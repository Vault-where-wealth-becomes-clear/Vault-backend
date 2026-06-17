import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import CurrencyType, PlanType


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    plan: PlanType
    base_currency: CurrencyType


class UserUpdate(BaseModel):
    name: str | None = None
    base_currency: CurrencyType | None = None
