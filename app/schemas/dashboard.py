from decimal import Decimal

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_usd: Decimal
    variation_pct: Decimal
    period: str
    insights: list[str]


class CategoryBreakdownItem(BaseModel):
    category: str
    amount_ars: Decimal
    amount_usd: Decimal | None
    pct_of_total: Decimal


class DashboardBreakdownResponse(BaseModel):
    period: str
    items: list[CategoryBreakdownItem]


class EvolutionPoint(BaseModel):
    month: str
    total_usd: Decimal


class DashboardEvolutionResponse(BaseModel):
    points: list[EvolutionPoint]
