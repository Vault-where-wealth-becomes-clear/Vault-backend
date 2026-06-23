import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FinancialSnapshot(Base):
    __tablename__ = "financial_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "period_month", name="uq_financial_snapshots_user_period"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    flujo_mensual: Mapped[dict | None] = mapped_column(JSONB)
    categorizacion: Mapped[dict | None] = mapped_column(JSONB)
    flujo_periodo: Mapped[dict | None] = mapped_column(JSONB)
    cartera: Mapped[dict | None] = mapped_column(JSONB)
    tablero_general: Mapped[dict | None] = mapped_column(JSONB)
    proyeccion: Mapped[dict | None] = mapped_column(JSONB)
    compromisos: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
