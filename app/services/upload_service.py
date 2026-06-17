import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UploadStatus
from app.models.transaction import Transaction
from app.models.upload import Upload


async def count_review_items(db: AsyncSession, upload_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.upload_id == upload_id, Transaction.needs_review.is_(True))
    )


def build_sqs_message(upload: Upload, user_id: uuid.UUID, account_type: str) -> dict:
    return {
        "upload_id": str(upload.id),
        "user_id": str(user_id),
        "account_type": account_type,
        "period_month": upload.period_month.isoformat(),
        "s3_key_pdf": upload.s3_key_pdf,
    }


async def get_status_payload(db: AsyncSession, upload: Upload) -> dict:
    review_count = None
    if upload.status == UploadStatus.review:
        review_count = await count_review_items(db, upload.id)

    return {
        "upload_id": upload.id,
        "status": upload.status,
        "error_message": upload.error_message,
        "processed_at": upload.processed_at,
        "review_count": review_count,
    }
