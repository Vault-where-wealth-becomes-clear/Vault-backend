import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import CurrencyType


class InstallmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    description: str
    current_installment: int
    total_installments: int
    amount_per_installment: float
    currency: CurrencyType
    next_due_date: date | None


class InstallmentUpdate(BaseModel):
    amount_per_installment: Decimal | None = None
    total_installments: int | None = None
