import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CurrencyType

if TYPE_CHECKING:
    from app.models.installment import Installment


class Transaction(Base):
    __tablename__ = "transactions"
    # Cierra el hueco de idempotencia si un mensaje de SQS se redelivera
    # mientras el primer intento sigue corriendo: los dos intentos escriben
    # el mismo (upload_id, sort_order) y uno de los dos muere en el commit
    # en vez de duplicar el ledger. Las transacciones manuales tienen
    # upload_id NULL y en Postgres los NULL no colisionan entre si.
    __table_args__ = (
        UniqueConstraint("upload_id", "sort_order", name="uq_transactions_upload_sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount_ars: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[CurrencyType] = mapped_column(
        Enum(CurrencyType, name="currency_type"), nullable=False, default=CurrencyType.ARS
    )
    category: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    installment: Mapped["Installment | None"] = relationship(
        "Installment", uselist=False, viewonly=True, lazy="joined"
    )

    @property
    def current_installment(self) -> int | None:
        return self.installment.current_installment if self.installment else None

    @property
    def total_installments(self) -> int | None:
        return self.installment.total_installments if self.installment else None
