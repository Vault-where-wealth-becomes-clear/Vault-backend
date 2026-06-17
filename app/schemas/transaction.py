import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import CurrencyType


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    upload_id: uuid.UUID
    account_id: uuid.UUID
    date: date
    description: str
    amount_ars: Decimal
    amount_usd: Decimal | None
    currency: CurrencyType
    category: str | None
    confidence: Decimal | None
    needs_review: bool
    is_corrected: bool
    created_at: datetime


class TransactionUpdate(BaseModel):
    category: str
    remember_rule: bool = False
