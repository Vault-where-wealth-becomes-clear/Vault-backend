import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Enum, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import MepSource


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    period_month: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    mep_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    source: Mapped[MepSource] = mapped_column(
        Enum(MepSource, name="mep_source"), nullable=False, default=MepSource.manual
    )
    set_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
