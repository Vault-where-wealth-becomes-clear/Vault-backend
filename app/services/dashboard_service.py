from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_snapshot import FinancialSnapshot
from app.models.transaction import Transaction


@dataclass
class MonthSummary:
    total_usd: Decimal
    savings: Decimal
    by_category: dict[str, Decimal] = field(default_factory=dict)


async def get_month_summary(db: AsyncSession, user_id, period_month: date) -> MonthSummary:
    rows = await db.execute(
        select(
            Transaction.category,
            func.sum(Transaction.amount_ars).label("total_ars"),
            func.sum(Transaction.amount_usd).label("total_usd"),
        )
        .where(
            Transaction.user_id == user_id,
            extract("year", Transaction.date) == period_month.year,
            extract("month", Transaction.date) == period_month.month,
        )
        .group_by(Transaction.category)
    )

    by_category: dict[str, Decimal] = {}
    total_usd = Decimal("0")
    income_ars = Decimal("0")
    expense_ars = Decimal("0")

    for category, total_ars, total_usd_cat in rows:
        total_ars = total_ars or Decimal("0")
        by_category[category or "Sin categoria"] = abs(total_ars)
        total_usd += total_usd_cat or Decimal("0")
        if total_ars > 0:
            income_ars += total_ars
        else:
            expense_ars += total_ars

    savings = income_ars + expense_ars  # expense_ars ya es negativo
    return MonthSummary(total_usd=total_usd, savings=savings, by_category=by_category)


def generate_insights(
    current_month: MonthSummary,
    previous_month: MonthSummary | None,
) -> list[str]:
    """Genera insights en lenguaje humano usando templates. No usa IA."""
    insights = []

    if previous_month:
        for category, current_amount in current_month.by_category.items():
            prev_amount = previous_month.by_category.get(category, Decimal("0"))
            if prev_amount > 0:
                diff_pct = ((current_amount - prev_amount) / prev_amount) * 100
                if diff_pct > 20:
                    insights.append(f"Gastaste {diff_pct:.0f}% mas en {category} que el mes pasado")
                elif diff_pct < -20:
                    insights.append(
                        f"Gastaste {abs(diff_pct):.0f}% menos en {category} que el mes pasado"
                    )

    if current_month.savings > 0:
        insights.append(f"Ahorraste ${current_month.savings:,.0f} ARS este mes")

    portfolio_change = current_month.total_usd - (
        previous_month.total_usd if previous_month else Decimal("0")
    )
    if portfolio_change != 0:
        direction = "subio" if portfolio_change > 0 else "bajo"
        insights.append(f"Tu patrimonio {direction} USD {abs(portfolio_change):,.0f} este mes")

    return insights


def generate_snapshot_insights(
    snapshot: FinancialSnapshot | None,
    previous_snapshot: FinancialSnapshot | None,
) -> list[str]:
    """
    Templates en texto sobre los módulos de la skill, SIN llamar a Claude.
    Solo agrega insights para los módulos que efectivamente se hayan calculado.
    """
    insights: list[str] = []
    if snapshot is None:
        return insights

    if snapshot.categorizacion and previous_snapshot and previous_snapshot.categorizacion:
        insights += _compare_categories(snapshot.categorizacion, previous_snapshot.categorizacion)

    if snapshot.cartera:
        insights += _cartera_insights(snapshot.cartera)

    if snapshot.proyeccion:
        insights += _proyeccion_insights(snapshot.proyeccion)

    if snapshot.tablero_general and snapshot.tablero_general.get("alertas"):
        insights += [_translate_alert(a) for a in snapshot.tablero_general["alertas"]]

    return insights


def _compare_categories(categorizacion: dict, previous_categorizacion: dict) -> list[str]:
    insights = []
    current_by_category = categorizacion.get("gasto_neto_por_categoria", {})
    previous_by_category = previous_categorizacion.get("gasto_neto_por_categoria", {})
    for category, amount in current_by_category.items():
        prev_amount = previous_by_category.get(category, 0)
        if prev_amount:
            diff_pct = ((amount - prev_amount) / prev_amount) * 100
            if diff_pct > 20:
                insights.append(f"Gastaste {diff_pct:.0f}% mas en {category} que el mes pasado")
            elif diff_pct < -20:
                insights.append(
                    f"Gastaste {abs(diff_pct):.0f}% menos en {category} que el mes pasado"
                )
    return insights


def _cartera_insights(cartera: dict) -> list[str]:
    insights = []
    posiciones = cartera.get("posiciones", [])
    total_pl = sum(p.get("pl_periodo", 0) for p in posiciones)
    if total_pl > 0:
        insights.append(f"Tu cartera tuvo un resultado positivo de ${total_pl:,.0f} en el período")
    elif total_pl < 0:
        insights.append(
            f"Tu cartera tuvo un resultado negativo de ${abs(total_pl):,.0f} en el período"
        )
    return insights


def _proyeccion_insights(proyeccion: dict) -> list[str]:
    insights = []
    banda_media = proyeccion.get("banda_media")
    if banda_media is not None:
        insights.append(
            f"Proyectamos un patrimonio liquido de ${banda_media:,.0f} dentro de 3 meses"
        )
    return insights


def _translate_alert(alert: str) -> str:
    return alert
