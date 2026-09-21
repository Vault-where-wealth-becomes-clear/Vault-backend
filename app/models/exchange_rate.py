import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import MepSource


class ExchangeRate(Base):
    """TC MEP declarado por un usuario para un periodo.

    La tabla era global —una fila por periodo, sin dueño— pero se escribe
    desde el flujo normal de cada usuario: el frontend pide declarar el TC
    antes de subir un extracto. Con una sola fila compartida, redeclarar el
    TC de un mes reescribia los montos convertidos de *todos* los usuarios.
    Scopearla por usuario elimina ese cruce sin sacarle a nadie la capacidad
    de declarar su propio tipo de cambio.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("user_id", "period_month", name="uq_exchange_rates_user_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    mep_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # "Venta" — el valor que se usa en todos los calculos existentes (worker,
    # dashboard). buy_rate ("compra") es solo informativo.
    buy_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    source: Mapped[MepSource] = mapped_column(
        Enum(MepSource, name="mep_source"), nullable=False, default=MepSource.manual
    )
    set_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
