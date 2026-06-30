import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.s3 import S3Client, get_s3
from app.aws.sqs import SQSClient, get_sqs
from app.database import get_db
from app.limiter import limiter
from app.middleware.auth import get_current_user
from app.models.account import Account
from app.models.upload import Upload
from app.models.user import User
from app.schemas.upload import (
    PresignRequest,
    PresignResponse,
    UploadCreate,
    UploadRead,
    UploadStatusResponse,
)
from app.services.upload_service import (
    build_sqs_message,
    create_pending_module_requests,
    get_status_payload,
    resolve_modules_for_upload,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
}


def _content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _CONTENT_TYPES.get(ext, "application/octet-stream")


@router.post("/presign", response_model=PresignResponse)
@limiter.limit("10/hour")
async def generate_presign_url(
    request: Request,
    body: PresignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3: S3Client = Depends(get_s3),
):
    account = await db.scalar(
        select(Account).where(Account.id == body.account_id, Account.user_id == current_user.id)
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    extension = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else "pdf"
    s3_key = f"uploads/{current_user.id}/{body.period_month:%Y-%m}/{uuid.uuid4()}.{extension}"
    content_type = _content_type(body.filename)
    presigned_url = await s3.generate_presigned_url(s3_key, content_type, expires_in=300)

    upload = Upload(
        user_id=current_user.id,
        account_id=account.id,
        s3_key_pdf=s3_key,
        period_month=body.period_month,
        status="pending",
        requested_modules=[m.value for m in body.requested_modules],
    )
    db.add(upload)
    await db.flush()

    return PresignResponse(
        upload_id=upload.id,
        presigned_url=presigned_url,
        s3_key=s3_key,
        content_type=content_type,
    )


@router.post("", response_model=UploadRead, status_code=201)
async def register_upload(
    body: UploadCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sqs: SQSClient = Depends(get_sqs),
):
    upload = await db.scalar(
        select(Upload).where(Upload.id == body.upload_id, Upload.user_id == current_user.id)
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload no encontrado")

    account = await db.scalar(select(Account).where(Account.id == upload.account_id))

    resolved_modules = await resolve_modules_for_upload(
        db, current_user.id, upload.period_month, upload.requested_modules, current_user.plan.value
    )
    await create_pending_module_requests(db, upload.id, resolved_modules)
    await db.flush()

    sqs.send_message(
        build_sqs_message(upload, current_user.id, account.account_type.value, resolved_modules)
    )
    return upload


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    upload = await db.scalar(
        select(Upload).where(Upload.id == upload_id, Upload.user_id == current_user.id)
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload no encontrado")

    return await get_status_payload(db, upload)


@router.get("", response_model=list[UploadRead])
async def list_uploads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Upload).where(Upload.user_id == current_user.id).order_by(Upload.uploaded_at.desc())
    )
    return result.all()
