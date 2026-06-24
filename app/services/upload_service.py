import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.plans import filter_modules_by_plan
from app.models.enums import UploadStatus
from app.models.financial_snapshot import FinancialSnapshot
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.upload_module_request import UploadModuleRequest
from app.services.module_dependencies import MODULE_SNAPSHOT_FIELD, resolve_required_modules


async def count_review_items(db: AsyncSession, upload_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.upload_id == upload_id, Transaction.needs_review.is_(True))
    )


def build_sqs_message(upload: Upload, user_id: uuid.UUID, account_type: str, resolved_modules: list[str]) -> dict:
    return {
        "upload_id": str(upload.id),
        "user_id": str(user_id),
        "account_type": account_type,
        "period_month": upload.period_month.isoformat(),
        "s3_key_pdf": upload.s3_key_pdf,
        "requested_modules": resolved_modules,
    }


async def resolve_modules_for_upload(
    db: AsyncSession, user_id: uuid.UUID, period_month: date, requested_modules: list[str], user_plan: str
) -> list[str]:
    """
    Filtra por plan y agrega dependencias no satisfechas por el histórico del período,
    reusando lo que ya esté calculado en financial_snapshots para no recalcularlo.
    """
    allowed_modules = filter_modules_by_plan(requested_modules, user_plan)

    snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == user_id, FinancialSnapshot.period_month == period_month
        )
    )
    user_history = (
        {field: getattr(snapshot, field) for field in MODULE_SNAPSHOT_FIELD.values()} if snapshot else None
    )

    return resolve_required_modules(allowed_modules, user_history)


async def create_pending_module_requests(db: AsyncSession, upload_id: uuid.UUID, resolved_modules: list[str]) -> None:
    for module in resolved_modules:
        db.add(UploadModuleRequest(upload_id=upload_id, module=module, status=UploadStatus.pending))
    await db.flush()


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
        "pending_mep": upload.pending_mep,
    }
