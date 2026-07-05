import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import SkillModule, UploadStatus


class PresignRequest(BaseModel):
    account_id: uuid.UUID
    period_month: date
    filename: str
    requested_modules: list[SkillModule] = [SkillModule.flujo_mensual]

    @field_validator("requested_modules")
    @classmethod
    def _ensure_flujo_mensual(cls, value: list[SkillModule]) -> list[SkillModule]:
        if not value:
            raise ValueError("Debe seleccionar al menos un modulo")
        if SkillModule.flujo_mensual not in value:
            value = [SkillModule.flujo_mensual, *value]
        return value


class PresignResponse(BaseModel):
    upload_id: uuid.UUID
    presigned_url: str
    s3_key: str
    content_type: str


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
    requested_modules: list[str]
    pending_mep: bool
    opening_balance_ars: Decimal = Decimal("0")
    opening_balance_usd: Decimal = Decimal("0")
    closing_balance_ars: Decimal = Decimal("0")
    closing_balance_usd: Decimal = Decimal("0")
    uploaded_at: datetime
    processed_at: datetime | None


class UploadStatusResponse(BaseModel):
    upload_id: uuid.UUID
    status: UploadStatus
    error_message: str | None
    processed_at: datetime | None
    review_count: int | None = None
    pending_mep: bool = False
