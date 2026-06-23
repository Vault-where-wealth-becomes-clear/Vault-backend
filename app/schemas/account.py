import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccountType, CurrencyType


class AccountCreate(BaseModel):
    name: str
    account_type: AccountType
    institution: str | None = None
    currency: CurrencyType = CurrencyType.ARS
    current_balance: Decimal = Decimal("0")


class AccountUpdate(BaseModel):
    name: str | None = None
    institution: str | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    account_type: AccountType
    institution: str | None
    currency: CurrencyType
    current_balance: float
    is_active: bool
