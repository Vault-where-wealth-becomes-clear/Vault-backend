import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import UploadStatus


class PresignRequest(BaseModel):
    account_id: uuid.UUID
    period_month: date
    filename: str


class PresignResponse(BaseModel):
    upload_id: uuid.UUID
    presigned_url: str
    s3_key: str


class UploadCreate(BaseModel):
    upload_id: uuid.UUID
    s3_key: str


class UploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    period_month: date
    status: UploadStatus
    detected_bank: str | None
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None


class UploadStatusResponse(BaseModel):
    upload_id: uuid.UUID
    status: UploadStatus
    error_message: str | None
    processed_at: datetime | None
    review_count: int | None = None
