import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import CurrencyType


class CategoryLimitCreate(BaseModel):
    category: str
    limit_amount: Decimal
    currency: CurrencyType = CurrencyType.ARS
    alert_at_pct: int = 80


class CategoryLimitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    limit_amount: float
    currency: CurrencyType
    alert_at_pct: int
