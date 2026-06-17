import uuid
from datetime import datetime

from sqlalchemy import Enum, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CurrencyType, PlanType


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType, name="plan_type"), nullable=False, default=PlanType.free
    )
    base_currency: Mapped[CurrencyType] = mapped_column(
        Enum(CurrencyType, name="currency_type"), nullable=False, default=CurrencyType.USD
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
