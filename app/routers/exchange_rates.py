from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateRead
from app.services import audit_service
from app.services.mep_service import recalculate_period

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])


@router.get("", response_model=list[ExchangeRateRead])
async def list_exchange_rates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.scalars(
        select(ExchangeRate)
        .where(ExchangeRate.user_id == current_user.id)
        .order_by(ExchangeRate.period_month.desc())
    )
    return result.all()


@router.post("", response_model=ExchangeRateRead, status_code=201)
async def set_exchange_rate(
    body: ExchangeRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate = await db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.user_id == current_user.id,
            ExchangeRate.period_month == body.period_month,
        )
    )
    old_mep_rate = rate.mep_rate if rate else None
    if rate:
        rate.mep_rate = body.mep_rate
    else:
        rate = ExchangeRate(
            user_id=current_user.id,
            period_month=body.period_month,
            mep_rate=body.mep_rate,
            source="manual",
        )
        db.add(rate)

    await db.flush()

    await audit_service.record(
        db,
        user_id=current_user.id,
        actor_user_id=current_user.id,
        entity_type="exchange_rate",
        entity_id=rate.id,
        action="rate_updated" if old_mep_rate is not None else "rate_created",
        before={"mep_rate": float(old_mep_rate)} if old_mep_rate is not None else None,
        after={"mep_rate": float(rate.mep_rate)},
    )

    return rate


@router.post("/{period}/recalculate")
async def recalculate(
    period: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate = await db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.user_id == current_user.id,
            ExchangeRate.period_month == period,
        )
    )
    if not rate:
        raise HTTPException(status_code=404, detail="No hay TC MEP definido para ese periodo")

    updated = await recalculate_period(
        db, current_user.id, period, rate.mep_rate, actor_user_id=current_user.id
    )
    return {"updated": updated}
