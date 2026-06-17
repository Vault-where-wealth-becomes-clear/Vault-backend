from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.dashboard import (
    CategoryBreakdownItem,
    DashboardBreakdownResponse,
    DashboardEvolutionResponse,
    DashboardResponse,
    EvolutionPoint,
)
from app.services.dashboard_service import generate_insights, get_month_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _parse_period(period: str | None) -> date:
    if period:
        year, month = (int(p) for p in period.split("-"))
        return date(year, month, 1)
    today = date.today()
    return date(today.year, today.month, 1)


def _previous_month(period_month: date) -> date:
    return (period_month - timedelta(days=1)).replace(day=1)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    period: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    period_month = _parse_period(period)
    current = await get_month_summary(db, current_user.id, period_month)
    previous = await get_month_summary(db, current_user.id, _previous_month(period_month))

    variation_pct = Decimal("0")
    if previous.total_usd:
        variation_pct = ((current.total_usd - previous.total_usd) / previous.total_usd) * 100

    return DashboardResponse(
        total_usd=current.total_usd,
        variation_pct=variation_pct,
        period=period_month.strftime("%Y-%m"),
        insights=generate_insights(current, previous),
    )


@router.get("/breakdown", response_model=DashboardBreakdownResponse)
async def get_breakdown(
    period: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    period_month = _parse_period(period)
    summary = await get_month_summary(db, current_user.id, period_month)

    total_ars = sum(summary.by_category.values()) or Decimal("1")
    items = [
        CategoryBreakdownItem(
            category=category,
            amount_ars=amount,
            amount_usd=None,
            pct_of_total=(amount / total_ars) * 100,
        )
        for category, amount in summary.by_category.items()
    ]

    return DashboardBreakdownResponse(period=period_month.strftime("%Y-%m"), items=items)


@router.get("/evolution", response_model=DashboardEvolutionResponse)
async def get_evolution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    points = []
    period_month = date(today.year, today.month, 1)

    for _ in range(12):
        summary = await get_month_summary(db, current_user.id, period_month)
        points.append(EvolutionPoint(month=period_month.strftime("%Y-%m"), total_usd=summary.total_usd))
        period_month = _previous_month(period_month)

    points.reverse()
    return DashboardEvolutionResponse(points=points)
