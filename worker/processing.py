import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.aws.s3 import S3Client
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.account import Account
from app.models.category_rule import CategoryRule
from app.models.enums import SkillModule, UploadStatus
from app.models.exchange_rate import ExchangeRate
from app.models.financial_snapshot import FinancialSnapshot
from app.models.installment import Installment
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.upload_module_request import UploadModuleRequest
from app.services.module_dependencies import MODULE_SNAPSHOT_FIELD, resolve_required_modules
from worker.llm.client import call_llm_with_skill
from worker.llm.parser import parse_skill_response
from worker.llm.prompts import ACCOUNT_TYPE_CONTEXT
from worker.llm.skill_loader import build_skill_system_prompt
from worker.parser.bank_detector import detect_bank
from worker.parser.extractor import extract_text
from worker.processors.confidence import split_by_confidence
from worker.processors.installments import extract_installments
from worker.processors.mep_converter import apply_mep_conversion
from worker.processors.redaction import redact_sensitive_numbers


async def process_upload(message: dict) -> None:
    upload_id = uuid.UUID(message["upload_id"])
    user_id = uuid.UUID(message["user_id"])
    account_type = message["account_type"]
    period_month = date.fromisoformat(message["period_month"])
    s3_key = message["s3_key_pdf"]
    requested_modules = message.get("requested_modules") or [SkillModule.flujo_mensual.value]

    async with AsyncSessionLocal() as db:
        upload = await db.get(Upload, upload_id)
        if upload is None:
            return

        try:
            upload.status = UploadStatus.processing
            await db.commit()

            s3 = S3Client()
            file_bytes = await s3.download_bytes(s3_key)
            text = extract_text(file_bytes, s3_key)
            text = redact_sensitive_numbers(text)
            detected_bank = detect_bank(text)

            category_rules = await _get_category_rules(db, user_id)
            mep_rate = await _get_mep_rate(db, period_month)
            pending_mep = mep_rate is None
            effective_rate = mep_rate or Decimal("1")

            user_history = await _get_financial_snapshot(db, user_id, period_month)
            resolved_modules = resolve_required_modules(requested_modules, user_history)

            system_prompt = build_skill_system_prompt(resolved_modules)
            user_message = _build_user_message(
                text,
                account_type,
                category_rules,
                period_month.strftime("%Y-%m"),
                resolved_modules,
                user_history,
            )

            raw_response = call_llm_with_skill(user_message, system_prompt)
            result = parse_skill_response(raw_response)

            transactions = result["transacciones"]
            transactions = _apply_fiscal_rules(transactions)
            transactions = apply_mep_conversion(transactions, effective_rate)
            installments = extract_installments(transactions)
            auto_txns, review_txns = split_by_confidence(
                transactions, settings.confidence_threshold
            )
            await _save_transactions(db, upload, auto_txns + review_txns, account_type)
            await _save_installments(db, upload, installments)

            await _upsert_financial_snapshot(db, user_id, period_month, result)
            await _update_account_balances(db, upload, result)
            await _save_module_request_results(db, upload.id, resolved_modules, result)

            try:
                await s3.delete_object(s3_key)
            except Exception as cleanup_exc:
                print(f"[worker] no se pudo borrar {s3_key} de S3: {cleanup_exc}")

            upload.detected_bank = detected_bank
            upload.pending_mep = pending_mep
            upload.status = UploadStatus.review if review_txns else UploadStatus.done
            upload.processed_at = datetime.utcnow()
            await db.commit()
        except Exception as exc:
            await db.rollback()
            upload = await db.get(Upload, upload_id)
            upload.status = UploadStatus.error
            upload.error_message = str(exc)[:1000]
            await db.commit()
            raise


def _build_user_message(
    text: str,
    account_type: str,
    category_rules: dict[str, str],
    period_month: str,
    resolved_modules: list[str],
    user_history: dict | None,
) -> str:
    context = ACCOUNT_TYPE_CONTEXT.get(account_type, "")
    rules_str = ", ".join(f'"{k}": "{v}"' for k, v in category_rules.items())
    history_str = "ninguno (primer período cargado o sin dependencias resueltas previamente)"
    if user_history:
        relevant = {
            module: user_history[MODULE_SNAPSHOT_FIELD[module]]
            for module in resolved_modules
            if MODULE_SNAPSHOT_FIELD.get(module)
            and user_history.get(MODULE_SNAPSHOT_FIELD[module]) is not None
        }
        if relevant:
            history_str = str(relevant)

    return f"""account_type: {account_type}
period: {period_month}
context: {context}
category_rules_preapply: {{{rules_str}}}
modulos_a_procesar: {resolved_modules}
datos_previos_del_periodo_o_historicos: {history_str}

Texto del extracto:
{text}"""


async def _get_category_rules(db, user_id: uuid.UUID) -> dict[str, str]:
    rows = await db.scalars(select(CategoryRule).where(CategoryRule.user_id == user_id))
    return {row.keyword: row.category for row in rows}


async def _get_mep_rate(db, period_month: date) -> Decimal | None:
    rate = await db.scalar(select(ExchangeRate).where(ExchangeRate.period_month == period_month))
    return rate.mep_rate if rate else None


async def _get_financial_snapshot(db, user_id: uuid.UUID, period_month: date) -> dict | None:
    snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == user_id, FinancialSnapshot.period_month == period_month
        )
    )
    if snapshot is None:
        return None
    return {field: getattr(snapshot, field) for field in MODULE_SNAPSHOT_FIELD.values()}


async def _upsert_financial_snapshot(
    db, user_id: uuid.UUID, period_month: date, result: dict
) -> None:
    snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == user_id, FinancialSnapshot.period_month == period_month
        )
    )
    if snapshot is None:
        snapshot = FinancialSnapshot(user_id=user_id, period_month=period_month)
        db.add(snapshot)

    field_by_module = {
        SkillModule.flujo_mensual.value: "flujo_mensual",
        SkillModule.categorizacion_gasto.value: "categorizacion",
        SkillModule.flujo_periodo.value: "flujo_periodo",
        SkillModule.cuenta_comitente.value: "cartera",
        SkillModule.tablero_general.value: "tablero_general",
        SkillModule.proyeccion_patrimonial.value: "proyeccion",
        SkillModule.compromisos_futuros.value: "compromisos",
    }
    for module_key, snapshot_field in field_by_module.items():
        if module_key in result:
            setattr(snapshot, snapshot_field, result[module_key])

    snapshot.updated_at = datetime.utcnow()
    await db.flush()


async def _update_account_balances(db, upload: Upload, result: dict) -> None:
    flujo = result.get("flujo_mensual")
    if not flujo:
        return
    libro = flujo.get("libro_diario", {})
    if not libro or not isinstance(libro, dict):
        return

    account = await db.get(Account, upload.account_id)
    if not account:
        return

    entries = [(name, data) for name, data in libro.items() if isinstance(data, dict)]
    if not entries:
        return

    chosen = next((d for _, d in entries if d.get("reconciliacion_ok")), entries[0][1])
    saldo_final = chosen.get("saldo_final")
    if saldo_final is not None:
        account.current_balance = Decimal(str(saldo_final))
        await db.flush()
        print(f"[worker] cuenta '{account.name}': saldo_final → {saldo_final}")


async def _save_module_request_results(
    db, upload_id: uuid.UUID, resolved_modules: list[str], result: dict
) -> None:
    for module in resolved_modules:
        existing = await db.scalar(
            select(UploadModuleRequest).where(
                UploadModuleRequest.upload_id == upload_id, UploadModuleRequest.module == module
            )
        )
        result_json = result.get(module)
        if existing is None:
            existing = UploadModuleRequest(upload_id=upload_id, module=module)
            db.add(existing)
        existing.status = UploadStatus.done if result_json is not None else UploadStatus.error
        existing.result_json = result_json
        if result_json is None:
            existing.error_message = "La skill no devolvió datos para este módulo"
    await db.flush()


_CREDIT_CARD_TYPES = {"credit_card_ars", "credit_card_usd"}

_CC_PAYMENT_PATTERNS = (
    "SU PAGO EN PESOS",
    "SU PAGO EN DOLARES",
    "SU PAGO EN USD",
    "SU PAGO ANTERIOR",
    "PAGO MINIMO ANTERIOR",
    "PAGO MINIMO",
)


def _is_cc_payment(description: str) -> bool:
    upper = description.upper()
    return upper.startswith("SU PAGO") or any(p in upper for p in _CC_PAYMENT_PATTERNS)


def _apply_fiscal_rules(transactions: list[dict]) -> list[dict]:
    """
    Hard-correct fiscal DB./CR. lines regardless of LLM output:
    - DB.* → category=Impuestos, amount negative
    - CR.* → category=Impuestos, amount positive (bank credit, not an expense)
    """
    for txn in transactions:
        desc_upper = txn.get("description", "").upper().strip()
        if desc_upper.startswith("DB."):
            txn["category"] = "Impuestos"
            if txn.get("amount", 0) > 0:
                txn["amount"] = -txn["amount"]
        elif desc_upper.startswith("CR."):
            txn["category"] = "Impuestos"
            if txn.get("amount", 0) < 0:
                txn["amount"] = -txn["amount"]
                print(f"[worker] CR.* crédito fiscal — signo corregido a positivo: {txn['description']!r}")
    return transactions


def _dedup_transactions(transactions: list[dict], account_type: str) -> list[dict]:
    """Keep one entry per (description, date). For credit cards prefer native currency."""
    prefer_ars = account_type == "credit_card_ars"
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for txn in transactions:
        key = (txn.get("description", "").strip(), txn.get("date", ""))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(txn)

    result = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            result.append(group[0])
        else:
            if prefer_ars:
                ars = [t for t in group if t.get("currency") == "ARS"]
                chosen = ars[0] if ars else group[0]
            else:
                usd = [t for t in group if t.get("currency") == "USD"]
                chosen = usd[0] if usd else group[0]
            print(f"[worker] dedup: {len(group) - 1} duplicado(s) descartado(s) — '{key[0]}' {key[1]}")
            result.append(chosen)
    return result


async def _save_transactions(db, upload: Upload, transactions: list[dict], account_type: str = "") -> None:
    is_credit_card = account_type in _CREDIT_CARD_TYPES

    # Strip CC payment lines
    if is_credit_card:
        before = len(transactions)
        transactions = [t for t in transactions if not _is_cc_payment(t.get("description", ""))]
        if len(transactions) < before:
            print(f"[worker] excluidos {before - len(transactions)} pago(s) de tarjeta")

    # Dedup by (description, date)
    transactions = _dedup_transactions(transactions, account_type)

    for txn in transactions:
        row = Transaction(
            upload_id=upload.id,
            user_id=upload.user_id,
            account_id=upload.account_id,
            date=date.fromisoformat(txn["date"]),
            description=txn["description"],
            amount_ars=txn["amount_ars"],
            amount_usd=txn["amount_usd"],
            currency=txn.get("currency", "ARS"),
            category=txn.get("category", "").capitalize() or None,
            confidence=Decimal(str(txn.get("confidence", 0))),
            needs_review=txn["needs_review"],
        )
        db.add(row)
        await db.flush()
        txn["_id"] = row.id


async def _save_installments(db, upload: Upload, installments: list[dict]) -> None:
    for inst in installments:
        txn_id = inst["_txn_ref"].get("_id")
        if txn_id is None:
            continue
        db.add(
            Installment(
                transaction_id=txn_id,
                user_id=upload.user_id,
                description=inst["description"],
                current_installment=inst["current_installment"],
                total_installments=inst["total_installments"],
                amount_per_installment=inst["amount_per_installment"],
                currency=inst["currency"],
            )
        )
    await db.flush()
