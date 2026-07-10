import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.aws.s3 import S3Client
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.account import Account
from app.models.cartera_snapshot import CarteraSnapshot
from app.models.category_rule import CategoryRule
from app.models.enums import CurrencyType, InstrumentoTipo, SkillModule, UploadStatus
from app.models.exchange_rate import ExchangeRate
from app.models.financial_snapshot import FinancialSnapshot
from app.models.installment import Installment
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.upload_module_request import UploadModuleRequest
from app.services.module_dependencies import MODULE_SNAPSHOT_FIELD, resolve_required_modules
from worker.llm.client import call_llm_with_skill
from worker.llm.model_selector import select_model
from worker.llm.parser import parse_skill_response
from worker.llm.prompts import ACCOUNT_TYPE_CONTEXT
from worker.llm.skill_loader import build_skill_system_prompt
from worker.parser.bank_detector import detect_bank
from worker.parser.extractor import extract_text
from worker.processors.amount_verifier import verify_and_correct_amounts
from worker.processors.confidence import split_by_confidence
from worker.processors.installments import extract_installments
from worker.processors.ledger_verifier import (
    last_printed_saldo,
    parse_ledger_lines,
    reconciliation_gap,
    verify_and_correct_ledger,
)
from worker.processors.mep_converter import apply_mep_conversion
from worker.processors.redaction import redact_sensitive_numbers


async def process_upload(message: dict) -> None:
    upload_id = uuid.UUID(message["upload_id"])
    user_id = uuid.UUID(message["user_id"])
    account_type = message["account_type"]
    hint_period = date.fromisoformat(message["period_month"])  # user-selected hint only
    s3_key = message["s3_key_pdf"]
    requested_modules = message.get("requested_modules") or [SkillModule.flujo_mensual.value]

    async with AsyncSessionLocal() as db:
        upload = await db.get(Upload, upload_id)
        if upload is None:
            return
        account = await db.get(Account, upload.account_id)

        try:
            upload.status = UploadStatus.processing
            await db.commit()

            s3 = S3Client()
            file_bytes = await s3.download_bytes(s3_key)
            extracted_text = extract_text(file_bytes, s3_key)
            extracted_text = redact_sensitive_numbers(extracted_text)
            detected_bank = detect_bank(extracted_text)

            category_rules = await _get_category_rules(db, user_id)
            user_history = await _get_financial_snapshot(
                db, user_id, hint_period, account_id=upload.account_id
            )
            resolved_modules = resolve_required_modules(requested_modules, user_history)

            system_prompt = build_skill_system_prompt(resolved_modules)
            user_message = _build_user_message(
                extracted_text,
                account_type,
                category_rules,
                hint_period.strftime("%Y-%m"),
                resolved_modules,
                user_history,
            )

            model = select_model(extracted_text)
            print(f"[worker] modelo elegido: {model}")
            raw_response, llm_usage = call_llm_with_skill(user_message, system_prompt, model=model)
            result = parse_skill_response(raw_response)

            upload.llm_model_used = llm_usage["model"]
            upload.llm_input_tokens = llm_usage["input_tokens"]
            upload.llm_output_tokens = llm_usage["output_tokens"]
            upload.llm_thinking_tokens = llm_usage["thinking_tokens"]
            upload.llm_cache_read_tokens = llm_usage["cache_read_tokens"]
            upload.llm_cache_creation_tokens = llm_usage["cache_creation_tokens"]

            raw_transactions = result["transacciones"]
            raw_transactions = verify_and_correct_amounts(raw_transactions, extracted_text)
            if account_type not in _CREDIT_CARD_ACCOUNT_TYPES:
                ledger_lines = parse_ledger_lines(extracted_text)
                if ledger_lines and len(ledger_lines) != len(raw_transactions):
                    # No alinear en silencio: si el LLM se comió movimientos
                    # (típicamente todo un mes en un PDF consolidado), el
                    # verificador y la reconciliación quedan ciegos porque
                    # ambos dependen del mismo alineamiento posicional. Mejor
                    # fallar fuerte acá — un reintento normalmente resuelve
                    # esto — que guardar un período incompleto como "listo".
                    raise ValueError(
                        f"El LLM devolvió {len(raw_transactions)} transacciones pero el "
                        f"extracto tiene {len(ledger_lines)} movimientos de cuenta — "
                        "no concilian, no se guarda nada. Reintentá el procesamiento."
                    )
                raw_transactions = verify_and_correct_ledger(raw_transactions, extracted_text)
            raw_transactions = _apply_fiscal_rules(raw_transactions)
            raw_transactions = _apply_transfer_direction_rules(raw_transactions)

            if account_type in _CREDIT_CARD_ACCOUNT_TYPES:
                # Un resumen de tarjeta es siempre UN único período de
                # facturación, aunque las cuotas impriman la fecha de compra
                # original de cada consumo (puede ser de más de un año
                # atrás — ej. "19-May-25" para una cuota 12/12 que recién se
                # cobra en el resumen de abril 2026). Agrupar por fecha de
                # transacción crearía un período fantasma para esa fecha de
                # compra vieja, sin tipo de cambio MEP cargado, y tiraba
                # abajo toda la carga.
                txn_by_month = {hint_period.strftime("%Y-%m"): raw_transactions}
            else:
                # Group by detected month — ignores user-selected hint_period
                txn_by_month = _group_by_month(raw_transactions)
            months = sorted(txn_by_month.keys())
            if not months:
                raise ValueError("El LLM no devolvió transacciones con fechas válidas")

            # No inferir la moneda del account_type: "savings_box" y "cash" no
            # codifican moneda en el nombre (a diferencia de checking_usd/
            # credit_card_usd) y pueden ser ARS o USD según currency.
            is_usd_account = account.currency == CurrencyType.USD
            if account_type in _CREDIT_CARD_ACCOUNT_TYPES:
                opening_ars = _extract_tarjeta_remainder(result, is_usd=False)
                opening_usd = _extract_tarjeta_remainder(result, is_usd=True)
            else:
                opening_ars, opening_usd = _extract_opening_balance(result, is_usd_account)

            if len(months) > 1:
                print(f"[worker] PDF multi-período detectado: {months}")

            has_any_review = False
            # Saldo de cierre real (impreso) del sub-período anterior, para
            # encadenar el saldo inicial del siguiente en un PDF consolidado
            # multi-mes — sin esto, cada mes después del primero arrancaba en 0.
            carried_ars: Decimal | None = None
            carried_usd: Decimal | None = None

            # Saldo de cierre del último upload cerrado de esta cuenta (si lo
            # hay), para verificar que el saldo inicial de este PDF encadena
            # con el período anterior en vez de confiar ciegamente en lo que
            # el LLM extrajo de este documento nuevo.
            prior_upload = None
            if account_type not in _CREDIT_CARD_ACCOUNT_TYPES:
                first_period = date.fromisoformat(months[0] + "-01")
                prior_upload = await db.scalar(
                    select(Upload)
                    .where(
                        Upload.account_id == upload.account_id,
                        Upload.period_month < first_period,
                        Upload.status == UploadStatus.done,
                    )
                    .order_by(Upload.period_month.desc())
                    .limit(1)
                )

            for i, month_key in enumerate(months):
                review_notes: list[str] = []
                sub_period = date.fromisoformat(month_key + "-01")
                sub_txns_raw = txn_by_month[month_key]

                sub_mep = await _get_mep_rate(db, sub_period)  # exact or most-recent fallback
                if sub_mep is None:
                    raise ValueError(
                        f"Sin tipo de cambio MEP disponible para {sub_period} — cargá al menos un TC antes de procesar este upload"
                    )
                sub_rate = sub_mep

                sub_txns = apply_mep_conversion(list(sub_txns_raw), sub_rate)
                sub_installments = extract_installments(sub_txns)
                sub_auto, sub_review = split_by_confidence(sub_txns, settings.confidence_threshold)

                if i == 0:
                    sub_upload = upload
                    sub_upload.period_month = sub_period
                    sub_upload.opening_balance_ars = opening_ars
                    sub_upload.opening_balance_usd = opening_usd
                    sub_opening_ars, sub_opening_usd = opening_ars, opening_usd

                    if account_type not in _CREDIT_CARD_ACCOUNT_TYPES:
                        this_opening = opening_usd if is_usd_account else opening_ars
                        if prior_upload is None:
                            # Primera carga de esta cuenta: el saldo inicial tiene
                            # que salir del PDF, nunca asumirse en $0 en silencio.
                            if opening_ars == 0 and opening_usd == 0:
                                review_notes.append(
                                    "No se encontró el saldo inicial impreso en el extracto "
                                    "para el primer período cargado de esta cuenta — no se "
                                    "puede asumir $0. Revisá el PDF o cargá el saldo inicial "
                                    "manualmente."
                                )
                        else:
                            prior_closing = (
                                prior_upload.closing_balance_usd
                                if is_usd_account
                                else prior_upload.closing_balance_ars
                            )
                            if abs(this_opening - prior_closing) > Decimal("0.01"):
                                review_notes.append(
                                    f"El saldo inicial de este período "
                                    f"(${_format_ar_amount(this_opening)}) no coincide con "
                                    f"el saldo final del período anterior "
                                    f"(${_format_ar_amount(prior_closing)}). Revisar."
                                )
                else:
                    # PDFs consolidados (ej. resúmenes de CA que repiten meses
                    # anteriores) no deben duplicar un período que ya fue
                    # cargado por separado — solo se sintetizan sub-uploads
                    # para períodos realmente nuevos.
                    existing = await db.scalar(
                        select(Upload).where(
                            Upload.account_id == upload.account_id,
                            Upload.period_month == sub_period,
                            Upload.status == UploadStatus.done,
                        )
                    )
                    if existing is not None:
                        print(
                            f"[worker] {month_key} ya tiene una carga cerrada "
                            f"({existing.id}) para esta cuenta — se omite para no duplicar"
                        )
                        continue

                    sub_opening_ars = carried_ars if carried_ars is not None else Decimal("0")
                    sub_opening_usd = carried_usd if carried_usd is not None else Decimal("0")
                    sub_upload = Upload(
                        user_id=user_id,
                        account_id=upload.account_id,
                        s3_key_pdf=s3_key,
                        period_month=sub_period,
                        status=UploadStatus.processing,
                        requested_modules=upload.requested_modules,
                        opening_balance_ars=sub_opening_ars,
                        opening_balance_usd=sub_opening_usd,
                    )
                    db.add(sub_upload)
                    await db.flush()
                    print(f"[worker] sub-upload {sub_upload.id} creado para {month_key}")

                # sub_txns, not sub_auto + sub_review: split_by_confidence tags
                # needs_review in place but concatenating the two filtered views
                # would reorder same-date rows by confidence instead of by the
                # statement's real order — sub_txns keeps the original sequence.
                await _save_transactions(db, sub_upload, sub_txns, account_type)
                await _save_installments(db, sub_upload, sub_installments)

                sub_upload.detected_bank = detected_bank
                sub_upload.pending_mep = sub_mep is None
                sub_upload.status = UploadStatus.review if sub_review else UploadStatus.done
                sub_upload.processed_at = datetime.utcnow()
                has_any_review = has_any_review or bool(sub_review)

                if account_type not in _CREDIT_CARD_ACCOUNT_TYPES:
                    sub_opening = sub_opening_usd if is_usd_account else sub_opening_ars
                    gap = reconciliation_gap(sub_txns, sub_opening)
                    if gap is not None and abs(gap) > Decimal("0.01"):
                        gap_str = _format_ar_amount(abs(gap))
                        note = (
                            f"No concilia: créditos-débitos+saldo anterior difiere "
                            f"${gap_str} del saldo que figura impreso en el extracto "
                            f"para este período. Revisar movimientos."
                        )
                        print(f"[worker] {month_key}: {note}")
                        review_notes.append(note)

                    closing = last_printed_saldo(sub_txns)
                    if closing is not None:
                        if is_usd_account:
                            carried_usd = closing
                            sub_upload.closing_balance_usd = closing
                        else:
                            carried_ars = closing
                            sub_upload.closing_balance_ars = closing

                if review_notes:
                    sub_upload.status = UploadStatus.review
                    sub_upload.error_message = " | ".join(review_notes)
                    has_any_review = True

            # Snapshot and balances: last detected period wins
            last_period = date.fromisoformat(months[-1] + "-01")

            if result.get("cuenta_comitente"):
                result["cuenta_comitente"] = _normalize_cartera(result["cuenta_comitente"])
                await _upsert_cartera_snapshot(
                    db, upload.account_id, last_period, result["cuenta_comitente"]
                )

            await _upsert_financial_snapshot(db, user_id, last_period, result)
            await _update_account_balances(db, upload, result)
            await _save_module_request_results(db, upload.id, resolved_modules, result)

            try:
                await s3.delete_object(s3_key)
            except Exception as cleanup_exc:
                print(f"[worker] no se pudo borrar {s3_key} de S3: {cleanup_exc}")

            await db.commit()
        except Exception as exc:
            await db.rollback()
            upload = await db.get(Upload, upload_id)
            upload.status = UploadStatus.error
            upload.error_message = str(exc)[:1000]
            await db.commit()
            raise


def _format_ar_amount(value: Decimal) -> str:
    """1234.5 -> '1.234,50' (miles con punto, decimales con coma — formato AR)."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
    """Return MEP rate for the exact period, or the most recent prior rate. Never 1:1."""
    rate = await db.scalar(select(ExchangeRate).where(ExchangeRate.period_month == period_month))
    if rate:
        return rate.mep_rate
    # Fallback: most recent rate before this period
    rate = await db.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.period_month < period_month)
        .order_by(ExchangeRate.period_month.desc())
        .limit(1)
    )
    return rate.mep_rate if rate else None


async def _get_financial_snapshot(
    db, user_id: uuid.UUID, period_month: date, account_id: uuid.UUID | None = None
) -> dict | None:
    snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == user_id, FinancialSnapshot.period_month == period_month
        )
    )
    history = (
        {
            field: getattr(snapshot, field)
            for field in MODULE_SNAPSHOT_FIELD.values()
            if field != "cartera"
        }
        if snapshot is not None
        else {}
    )

    # cartera vive en su propia tabla, scoped por cuenta (una cuenta comitente no debe
    # pisar la de otra en el mismo mes) — se inyecta acá bajo la misma clave "cartera"
    # para que _build_user_message siga funcionando sin cambios en su lógica genérica.
    if account_id is not None:
        cartera_snap = await db.scalar(
            select(CarteraSnapshot).where(
                CarteraSnapshot.account_id == account_id,
                CarteraSnapshot.period_month == period_month,
            )
        )
        if cartera_snap is not None:
            history["cartera"] = {
                "nivel_detectado": cartera_snap.nivel_detectado,
                "posiciones": cartera_snap.posiciones,
                "rendimientos_netos_ars": cartera_snap.rendimientos_netos_ars,
                "retenciones_ars": cartera_snap.retenciones_ars,
                "delta_cartera_mes": cartera_snap.delta_cartera_mes,
            }

    return history or None


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
        SkillModule.tablero_general.value: "tablero_general",
        SkillModule.proyeccion_patrimonial.value: "proyeccion",
        SkillModule.compromisos_futuros.value: "compromisos",
    }
    for module_key, snapshot_field in field_by_module.items():
        if module_key in result:
            setattr(snapshot, snapshot_field, result[module_key])

    snapshot.updated_at = datetime.utcnow()
    await db.flush()


async def _upsert_cartera_snapshot(
    db, account_id: uuid.UUID, period_month: date, cartera: dict
) -> None:
    snapshot = await db.scalar(
        select(CarteraSnapshot).where(
            CarteraSnapshot.account_id == account_id, CarteraSnapshot.period_month == period_month
        )
    )
    if snapshot is None:
        snapshot = CarteraSnapshot(account_id=account_id, period_month=period_month)
        db.add(snapshot)

    snapshot.nivel_detectado = cartera.get("nivel_detectado", 1)
    snapshot.posiciones = cartera.get("posiciones", [])
    snapshot.rendimientos_netos_ars = cartera.get("rendimientos_netos_ars")
    snapshot.retenciones_ars = cartera.get("retenciones_ars")
    snapshot.delta_cartera_mes = cartera.get("delta_cartera_mes")
    snapshot.updated_at = datetime.utcnow()
    await db.flush()


_CREDIT_CARD_ACCOUNT_TYPES = {"credit_card_ars", "credit_card_usd"}


def _extract_tarjeta_remainder(result: dict, is_usd: bool) -> Decimal:
    """Remanente sin pagar del período anterior de la tarjeta: saldo_anterior - pago.

    Las tarjetas de crédito quedan excluidas del libro_diario por diseño (se
    procesan en devengado, ver 01_flujo_mensual.md), así que su SALDO ANTERIOR
    nunca llega por ese camino. Lo leemos del campo dedicado `saldo_tarjeta` y
    lo guardamos en opening_balance_ars/usd para que el frontend lo sume al
    total del período — si no, un saldo no cancelado del mes previo desaparece
    silenciosamente del total mostrado.
    """
    saldo_tarjeta = result.get("saldo_tarjeta") or {}
    suffix = "usd" if is_usd else "ars"
    anterior = saldo_tarjeta.get(f"saldo_anterior_{suffix}")
    if not anterior:
        return Decimal("0")
    pago = saldo_tarjeta.get(f"pago_{suffix}") or 0
    remainder = Decimal(str(anterior)) - Decimal(str(pago))
    return remainder if remainder > 0 else Decimal("0")


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

    if account.account_type.value in _CREDIT_CARD_ACCOUNT_TYPES:
        print(
            f"[worker] cuenta '{account.name}' es tarjeta de crédito — current_balance no actualizado"
        )
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


def _group_by_month(transactions: list[dict]) -> dict[str, list[dict]]:
    """Group transactions by 'YYYY-MM' extracted from each transaction's date field."""
    groups: dict[str, list[dict]] = {}
    for txn in transactions:
        month_key = (txn.get("date") or "")[:7]
        if month_key:
            groups.setdefault(month_key, []).append(txn)
    return groups


def _extract_opening_balance(result: dict, is_usd: bool = False) -> tuple[Decimal, Decimal]:
    """Read saldo_inicial from flujo_mensual.libro_diario (first valid account entry)."""
    libro = (result.get("flujo_mensual") or {}).get("libro_diario") or {}
    for account_data in libro.values():
        if not isinstance(account_data, dict):
            continue
        val = account_data.get("saldo_inicial")
        if val is not None and val != 0:
            saldo = Decimal(str(val))
            return (Decimal("0"), saldo) if is_usd else (saldo, Decimal("0"))
    return Decimal("0"), Decimal("0")


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


def _normalize_cartera(cartera: dict) -> dict:
    """
    Agregados derivados de cuenta_comitente que nunca se confían al LLM (ver reglas en
    _output_contract.md): tipo de instrumento coercionado a un valor válido, y % cartera
    calculado desde valor_base_ars de todas las posiciones.
    """
    tipos_validos = {t.value for t in InstrumentoTipo}
    posiciones = cartera.get("posiciones") or []
    for pos in posiciones:
        if pos.get("tipo") not in tipos_validos:
            pos["tipo"] = InstrumentoTipo.otro.value

    total = sum(Decimal(str(p.get("valor_base_ars", 0) or 0)) for p in posiciones)
    for pos in posiciones:
        valor = Decimal(str(pos.get("valor_base_ars", 0) or 0))
        pos["pct_cartera"] = float(valor / total) if total else 0.0

    return cartera


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
                print(
                    f"[worker] CR.* crédito fiscal — signo corregido a positivo: {txn['description']!r}"
                )
    return transactions


def _apply_transfer_direction_rules(transactions: list[dict]) -> list[dict]:
    """
    Hard-correct la dirección de movimientos cuyo signo es inequívoco por el
    texto de la descripción, sin importar lo que haya decidido el LLM — típico
    en extractos de Mercado Pago, donde se vio "Transferencia recibida" y
    "Transferencia enviada" con el signo invertido entre sí:
    - "Transferencia recibida..." / "Rendimientos...": SIEMPRE crédito (positivo) — es plata que entra.
    - "Transferencia enviada...": SIEMPRE débito (negativo) — es plata que sale.
    """
    for txn in transactions:
        desc = txn.get("description", "").strip().lower()
        amount = txn.get("amount")
        if amount is None:
            continue
        if desc.startswith("transferencia recibida") or desc.startswith("rendimientos"):
            if amount < 0:
                print(
                    f"[worker] dirección corregida a crédito: {txn['description']!r} ({amount} -> {abs(amount)})"
                )
                txn["amount"] = abs(amount)
        elif desc.startswith("transferencia enviada"):
            if amount > 0:
                print(
                    f"[worker] dirección corregida a débito: {txn['description']!r} ({amount} -> {-abs(amount)})"
                )
                txn["amount"] = -abs(amount)
    return transactions


def _dedup_transactions(transactions: list[dict], account_type: str) -> list[dict]:
    """Collapse only the LLM's ARS/USD double-emission bug: the same PDF row
    reported twice for one (description, date), once in each currency.
    Distinct transactions that legitimately share description+date — e.g. the
    same merchant billed twice the same day, or repeated cuotas — are never
    merged, since they differ in amount/cupón and must both be kept."""
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
        currencies = {t.get("currency") for t in group}
        if len(group) == 2 and currencies == {"ARS", "USD"}:
            if prefer_ars:
                chosen = next(t for t in group if t.get("currency") == "ARS")
            else:
                chosen = next(t for t in group if t.get("currency") == "USD")
            print(f"[worker] dedup: fila duplicada ARS/USD descartada — '{key[0]}' {key[1]}")
            result.append(chosen)
        else:
            result.extend(group)
    return result


async def _save_transactions(
    db, upload: Upload, transactions: list[dict], account_type: str = ""
) -> None:
    is_credit_card = account_type in _CREDIT_CARD_TYPES

    # Strip CC payment lines
    if is_credit_card:
        before = len(transactions)
        transactions = [t for t in transactions if not _is_cc_payment(t.get("description", ""))]
        if len(transactions) < before:
            print(f"[worker] excluidos {before - len(transactions)} pago(s) de tarjeta")

    # Dedup by (description, date)
    transactions = _dedup_transactions(transactions, account_type)

    for i, txn in enumerate(transactions):
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
            sort_order=i,
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
