from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.financial_snapshot import FinancialSnapshot
from app.models.user import User
from app.schemas.dashboard import (
    CategoryBreakdownItem,
    DashboardBreakdownResponse,
    DashboardEvolutionResponse,
    DashboardResponse,
    EvolutionPoint,
    FullDashboardResponse,
)
from app.services.dashboard_service import (
    generate_insights,
    generate_snapshot_insights,
    get_month_summary,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _previous_month(period_month: date) -> date:
    return (period_month - timedelta(days=1)).replace(day=1)


async def _resolve_period(period: str | None, db: AsyncSession, user_id) -> date:
    if period:
        year, month = (int(p) for p in period.split("-"))
        return date(year, month, 1)
    latest = await db.scalar(
        select(FinancialSnapshot.period_month)
        .where(FinancialSnapshot.user_id == user_id)
        .order_by(FinancialSnapshot.period_month.desc())
        .limit(1)
    )
    if latest:
        return latest
    today = date.today()
    return date(today.year, today.month, 1)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    period: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    period_month = await _resolve_period(period, db, current_user.id)
    current = await get_month_summary(db, current_user.id, period_month)
    previous = await get_month_summary(db, current_user.id, _previous_month(period_month))

    snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == current_user.id,
            FinancialSnapshot.period_month == period_month,
        )
    )
    if snapshot and snapshot.tablero_general:
        tg_usd = snapshot.tablero_general.get("patrimonio_total_usd")
        if tg_usd is not None:
            current.total_usd = Decimal(str(tg_usd))

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
    period_month = await _resolve_period(period, db, current_user.id)
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
        points.append(
            EvolutionPoint(month=period_month.strftime("%Y-%m"), total_usd=summary.total_usd)
        )
        period_month = _previous_month(period_month)

    points.reverse()
    return DashboardEvolutionResponse(points=points)


@router.get("/full", response_model=FullDashboardResponse)
async def get_full_dashboard(
    period: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve el snapshot consolidado del período: todos los módulos que se hayan
    calculado hasta ahora para ese usuario y período, tal como están guardados en
    financial_snapshots. El frontend arma las secciones del dashboard según qué
    claves vengan presentes (no todas siempre van).
    """
    period_month = await _resolve_period(period, db, current_user.id)
    snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == current_user.id,
            FinancialSnapshot.period_month == period_month,
        )
    )
    if not snapshot:
        # Sin snapshot todavia no es un error: es el estado inicial antes de procesar
        # el primer upload del periodo. El frontend ya sabe renderizar el CTA vacio
        # por modulo cuando estas claves vienen en null.
        return FullDashboardResponse(period=period_month, insights=[])

    previous_snapshot = await db.scalar(
        select(FinancialSnapshot).where(
            FinancialSnapshot.user_id == current_user.id,
            FinancialSnapshot.period_month == _previous_month(period_month),
        )
    )

    return FullDashboardResponse(
        period=period_month,
        flujo_mensual=snapshot.flujo_mensual,
        categorizacion=snapshot.categorizacion,
        flujo_periodo=snapshot.flujo_periodo,
        cartera=snapshot.cartera,
        tablero_general=snapshot.tablero_general,
        proyeccion=snapshot.proyeccion,
        compromisos=snapshot.compromisos,
        insights=generate_snapshot_insights(snapshot, previous_snapshot),
    )
