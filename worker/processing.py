import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.aws.s3 import S3Client
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.category_rule import CategoryRule
from app.models.enums import UploadStatus
from app.models.exchange_rate import ExchangeRate
from app.models.installment import Installment
from app.models.transaction import Transaction
from app.models.upload import Upload
from worker.llm.client import call_llm
from worker.llm.parser import parse_llm_response
from worker.llm.prompts import SYSTEM_PROMPT, build_prompt
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

            prompt = build_prompt(account_type, text, category_rules, period_month.strftime("%Y-%m"))
            raw_response = call_llm(prompt, SYSTEM_PROMPT)
            transactions = parse_llm_response(raw_response)

            transactions = apply_mep_conversion(transactions, effective_rate)
            installments = extract_installments(transactions)
            auto_txns, review_txns = split_by_confidence(transactions, settings.confidence_threshold)

            await _save_transactions(db, upload, auto_txns + review_txns)
            await _save_installments(db, upload, installments)

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


async def _get_category_rules(db, user_id: uuid.UUID) -> dict[str, str]:
    rows = await db.scalars(select(CategoryRule).where(CategoryRule.user_id == user_id))
    return {row.keyword: row.category for row in rows}


async def _get_mep_rate(db, period_month: date) -> Decimal | None:
    rate = await db.scalar(select(ExchangeRate).where(ExchangeRate.period_month == period_month))
    return rate.mep_rate if rate else None


async def _save_transactions(db, upload: Upload, transactions: list[dict]) -> None:
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
            category=txn.get("category"),
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
