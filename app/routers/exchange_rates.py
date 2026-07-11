from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.exchange_rate import ExchangeRate
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateRead
from app.services.mep_service import recalculate_period

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])


@router.get("", response_model=list[ExchangeRateRead])
async def list_exchange_rates(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.scalars(select(ExchangeRate).order_by(ExchangeRate.period_month.desc()))
    return result.all()


@router.post("", response_model=ExchangeRateRead, status_code=201)
async def set_exchange_rate(
    body: ExchangeRateCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    rate = await db.scalar(
        select(ExchangeRate).where(ExchangeRate.period_month == body.period_month)
    )
    if rate:
        rate.mep_rate = body.mep_rate
        rate.source = body.source
    else:
        rate = ExchangeRate(
            period_month=body.period_month, mep_rate=body.mep_rate, source=body.source
        )
        db.add(rate)

    await db.flush()
    return rate


@router.post("/{period}/recalculate")
async def recalculate(
    period: date,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    rate = await db.scalar(select(ExchangeRate).where(ExchangeRate.period_month == period))
    if not rate:
        raise HTTPException(status_code=404, detail="No hay TC MEP definido para ese periodo")

    updated = await recalculate_period(db, period, rate.mep_rate)
    return {"updated": updated}
