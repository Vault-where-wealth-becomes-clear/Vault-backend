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
    DashboardMonthlySeriesResponse,
    DashboardResponse,
    EvolutionPoint,
    FullDashboardResponse,
)
from app.services.dashboard_service import (
    generate_insights,
    generate_snapshot_insights,
    get_flujo_del_mes,
    get_month_summary,
    get_monthly_series,
    get_patrimonio_actual,
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

    # Patrimony from current_balance of non-credit-card accounts (source of truth)
    current.total_usd = await get_patrimonio_actual(db, current_user.id, period_month)
    previous.total_usd = await get_patrimonio_actual(
        db, current_user.id, _previous_month(period_month)
    )

    variation_pct = Decimal("0")
    if previous.total_usd:
        variation_pct = ((current.total_usd - previous.total_usd) / previous.total_usd) * 100

    flujo = await get_flujo_del_mes(db, current_user.id, period_month)
    previous_flujo = await get_flujo_del_mes(db, current_user.id, _previous_month(period_month))

    return DashboardResponse(
        total_usd=current.total_usd,
        variation_pct=variation_pct,
        period=period_month.strftime("%Y-%m"),
        insights=generate_insights(current, previous, flujo, previous_flujo),
        flujo_del_mes=flujo,
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
    period: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    anchor = await _resolve_period(period, db, current_user.id)

    # Build last-6-month window ending at anchor
    months: list[date] = []
    m = anchor
    for _ in range(6):
        months.append(m)
        m = _previous_month(m)
    months.reverse()  # oldest → newest

    points: list[EvolutionPoint] = []
    for month in months:
        if month == anchor:
            # Current period: use live current_balance source
            val = await get_patrimonio_actual(db, current_user.id, month)
            if val > 0:
                points.append(EvolutionPoint(month=month.strftime("%Y-%m"), total_usd=float(val)))
        else:
            # Past period: use most recent snapshot for that calendar month
            snap = await db.scalar(
                select(FinancialSnapshot)
                .where(
                    FinancialSnapshot.user_id == current_user.id,
                    # Match exacto de period_month — ver nota en
                    # dashboard_service._get_patrimonio_for_series.
                    FinancialSnapshot.period_month == month,
                    FinancialSnapshot.tablero_general.isnot(None),
                )
                .order_by(FinancialSnapshot.period_month.desc())
                .limit(1)
            )
            if snap and snap.tablero_general:
                pat = snap.tablero_general.get("patrimonio_total_usd")
                if pat is not None and float(pat) > 0:
                    points.append(
                        EvolutionPoint(month=month.strftime("%Y-%m"), total_usd=float(pat))
                    )

    return DashboardEvolutionResponse(points=points)


@router.get("/monthly-series", response_model=DashboardMonthlySeriesResponse)
async def get_monthly_series_endpoint(
    period: str | None = Query(default=None),
    months: int = Query(default=6, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    anchor = await _resolve_period(period, db, current_user.id)
    points = await get_monthly_series(db, current_user.id, anchor, count=months)
    return DashboardMonthlySeriesResponse(points=points)


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
