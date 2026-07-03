from datetime import date as date_type
from typing import Any

from pydantic import BaseModel


class FlujoDelMes(BaseModel):
    ingresos_ars: float
    egresos_ars: float
    resultado_ars: float
    ingresos_usd: float
    egresos_usd: float


class DashboardResponse(BaseModel):
    total_usd: float
    variation_pct: float
    period: str
    insights: list[str]
    flujo_del_mes: FlujoDelMes | None = None


class CategoryBreakdownItem(BaseModel):
    category: str
    amount_ars: float
    amount_usd: float | None
    pct_of_total: float


class DashboardBreakdownResponse(BaseModel):
    period: str
    items: list[CategoryBreakdownItem]


class EvolutionPoint(BaseModel):
    month: str
    total_usd: float


class DashboardEvolutionResponse(BaseModel):
    points: list[EvolutionPoint]


class MonthlySeriesPoint(BaseModel):
    month: str
    ingresos_ars: float
    egresos_ars: float
    resultado_ars: float
    resultado_usd: float | None
    gasto_usd: float | None
    patrimonio_usd: float | None
    cartera_usd: float | None


class DashboardMonthlySeriesResponse(BaseModel):
    points: list[MonthlySeriesPoint]


class FullDashboardResponse(BaseModel):
    period: date_type
    flujo_mensual: dict[str, Any] | None = None
    categorizacion: dict[str, Any] | None = None
    flujo_periodo: dict[str, Any] | None = None
    cartera: dict[str, Any] | None = None
    tablero_general: dict[str, Any] | None = None
    proyeccion: dict[str, Any] | None = None
    compromisos: dict[str, Any] | None = None
    insights: list[str] = []
