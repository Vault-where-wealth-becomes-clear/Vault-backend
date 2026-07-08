import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CarteraSnapshot(Base):
    __tablename__ = "cartera_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "period_month", name="uq_cartera_snapshots_account_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    nivel_detectado: Mapped[int] = mapped_column(Integer, nullable=False)
    posiciones: Mapped[list] = mapped_column(JSONB, nullable=False)
    rendimientos_netos_ars: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    retenciones_ars: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    delta_cartera_mes: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
