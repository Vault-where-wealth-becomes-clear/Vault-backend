import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CurrencyType


class Installment(Base):
    __tablename__ = "installments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    current_installment: Mapped[int] = mapped_column(Integer, nullable=False)
    total_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_per_installment: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[CurrencyType] = mapped_column(
        Enum(CurrencyType, name="currency_type"), nullable=False, default=CurrencyType.ARS
    )
    next_due_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
