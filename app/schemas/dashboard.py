from datetime import date as date_type
from typing import Any

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_usd: float
    variation_pct: float
    period: str
    insights: list[str]


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
