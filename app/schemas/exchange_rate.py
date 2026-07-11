import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import MepSource


class ExchangeRateCreate(BaseModel):
    period_month: date
    mep_rate: Decimal
    source: MepSource = MepSource.manual


class ExchangeRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_month: date
    mep_rate: float
    source: MepSource
    set_at: datetime
