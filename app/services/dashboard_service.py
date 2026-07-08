from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.cartera_snapshot import CarteraSnapshot
from app.models.enums import AccountType, CurrencyType
from app.models.exchange_rate import ExchangeRate
from app.models.financial_snapshot import FinancialSnapshot
from app.models.transaction import Transaction


@dataclass
class MonthSummary:
    total_usd: Decimal
    savings: Decimal
    by_category: dict[str, Decimal] = field(default_factory=dict)


_CREDIT_CARD_TYPES = [AccountType.credit_card_ars, AccountType.credit_card_usd]

# Cuenta comitente tiene su propio concepto de resultado (rendimientos, resultado
# realizado, Δ de valuación) — nunca debe mezclarse con gasto/ingreso/flujo bancario,
# ni siquiera si alguna vez queda una transacción mal asociada a esa cuenta.
_EXCLUDED_FROM_CASH_FLOW = [*_CREDIT_CARD_TYPES, AccountType.broker]


def _prev_month(period_month: date) -> date:
    return (period_month - timedelta(days=1)).replace(day=1)


async def _get_mep_for_month(db: AsyncSession, period_month: date) -> Decimal | None:
    mep = await db.scalar(
        select(ExchangeRate.mep_rate).where(ExchangeRate.period_month == period_month)
    )
    if mep is None:
        mep = await db.scalar(
            select(ExchangeRate.mep_rate)
            .where(ExchangeRate.period_month <= period_month)
            .order_by(ExchangeRate.period_month.desc())
            .limit(1)
        )
    return Decimal(str(mep)) if mep is not None else None


async def get_patrimonio_actual(db: AsyncSession, user_id, period_month: date) -> Decimal:
    """
    Suma current_balance de todas las cuentas activas del usuario,
    excluyendo tarjetas de crédito. Convierte saldos ARS a USD con el MEP del período.
    """
    mep = await _get_mep_for_month(db, period_month)
    if mep is None:
        return Decimal("0")  # no MEP loaded at all — return 0 rather than inflate with 1:1

    rows = await db.execute(
        select(Account.current_balance, Account.currency)
        .where(
            Account.user_id == user_id,
            Account.is_active.is_(True),
            Account.account_type.not_in(_CREDIT_CARD_TYPES),
            Account.current_balance.isnot(None),
        )
    )
    total = Decimal("0")
    for balance, currency in rows:
        b = balance or Decimal("0")
        total += (b / mep).quantize(Decimal("0.0001")) if currency == CurrencyType.ARS else b
    return total


async def get_month_summary(db: AsyncSession, user_id, period_month: date) -> MonthSummary:
    # Spending by category — all accounts incl. credit cards (real expenses); excluye
    # solo broker (cartera tiene su propio concepto de resultado, nunca gasto/ingreso).
    rows = await db.execute(
        select(
            Transaction.category,
            func.sum(Transaction.amount_ars).label("total_ars"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Transaction.user_id == user_id,
            extract("year", Transaction.date) == period_month.year,
            extract("month", Transaction.date) == period_month.month,
            Account.account_type != AccountType.broker,
        )
        .group_by(Transaction.category)
    )

    by_category: dict[str, Decimal] = {}
    income_ars = Decimal("0")
    expense_ars = Decimal("0")

    for category, total_ars in rows:
        total_ars = total_ars or Decimal("0")
        by_category[category or "Sin categoria"] = abs(total_ars)
        if total_ars > 0:
            income_ars += total_ars
        else:
            expense_ars += total_ars

    savings = income_ars + expense_ars  # expense_ars ya es negativo

    # Patrimony in USD — exclude credit cards (liabilities, not assets) and broker
    # (cartera no aporta acá, tiene su propio valor de cartera_usd separado).
    usd_row = await db.execute(
        select(func.sum(Transaction.amount_usd))
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Transaction.user_id == user_id,
            extract("year", Transaction.date) == period_month.year,
            extract("month", Transaction.date) == period_month.month,
            Account.account_type.not_in(_EXCLUDED_FROM_CASH_FLOW),
        )
    )
    total_usd = usd_row.scalar() or Decimal("0")

    # Add balances of accounts that don't generate transactions (cash and crypto in USD)
    cash_rows = await db.execute(
        select(Account.current_balance, Account.currency).where(
            Account.user_id == user_id,
            Account.is_active.is_(True),
            Account.account_type.in_([AccountType.cash, AccountType.crypto]),
            Account.currency == CurrencyType.USD,
        )
    )
    for balance, _ in cash_rows:
        total_usd += balance or Decimal("0")

    return MonthSummary(total_usd=total_usd, savings=savings, by_category=by_category)


async def get_flujo_del_mes(
    db: AsyncSession, user_id, period_month: date
) -> dict[str, Decimal]:
    """Sum ingresos/egresos from non-CC, non-broker account transactions for the period —
    cartera tiene su propio resultado (ver MonthlyCarteraFlujoLine en el frontend), no se
    mezcla con el flujo de cuentas bancarias."""
    row = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(case((Transaction.amount_ars > 0, Transaction.amount_ars))),
                    Decimal("0"),
                ).label("ingresos_ars"),
                func.coalesce(
                    func.sum(case((Transaction.amount_ars < 0, Transaction.amount_ars))),
                    Decimal("0"),
                ).label("egresos_ars"),
                func.coalesce(
                    func.sum(case((Transaction.amount_usd > 0, Transaction.amount_usd))),
                    Decimal("0"),
                ).label("ingresos_usd"),
                func.coalesce(
                    func.sum(case((Transaction.amount_usd < 0, Transaction.amount_usd))),
                    Decimal("0"),
                ).label("egresos_usd"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Transaction.user_id == user_id,
                extract("year", Transaction.date) == period_month.year,
                extract("month", Transaction.date) == period_month.month,
                Account.account_type.not_in(_EXCLUDED_FROM_CASH_FLOW),
            )
        )
    ).one()
    ing = row.ingresos_ars or Decimal("0")
    egr = row.egresos_ars or Decimal("0")
    return {
        "ingresos_ars": float(ing),
        "egresos_ars": float(egr),
        "resultado_ars": float(ing + egr),
        "ingresos_usd": float(row.ingresos_usd or Decimal("0")),
        "egresos_usd": float(row.egresos_usd or Decimal("0")),
    }


async def _get_patrimonio_for_series(db: AsyncSession, user_id, month: date, anchor: date) -> float | None:
    """Live current_balance para el mes ancla (más reciente), snapshot LLM para meses pasados."""
    if month == anchor:
        val = await get_patrimonio_actual(db, user_id, month)
        return float(val) if val > 0 else None

    snap = await db.scalar(
        select(FinancialSnapshot)
        .where(
            FinancialSnapshot.user_id == user_id,
            # Match exacto de period_month, no year/month: un snapshot con
            # period_month distinto de "primero del mes" (datos viejos de
            # prueba, ej. 2026-01-02) coincidía igual por año/mes y, al ser
            # una fecha "más reciente", le ganaba en el order_by desc al
            # snapshot real del mes — devolviendo el patrimonio vacío/viejo
            # en vez del real.
            FinancialSnapshot.period_month == month,
            FinancialSnapshot.tablero_general.isnot(None),
        )
        .order_by(FinancialSnapshot.period_month.desc())
        .limit(1)
    )
    if snap and snap.tablero_general:
        pat = snap.tablero_general.get("patrimonio_total_usd")
        if pat is not None and float(pat) > 0:
            return float(pat)
    return None


async def _get_cartera_usd_for_month(db: AsyncSession, user_id, month: date, mep: Decimal | None) -> float | None:
    """
    Valuación de cartera del mes, convertida a USD con el MEP del período — sumada
    across TODAS las cuentas comitente del usuario (cada una guarda su propia cartera
    en cartera_snapshots, ver CarteraSnapshot; acá se agrega para el gráfico general).
    """
    if mep is None:
        return None
    snapshots = await db.scalars(
        select(CarteraSnapshot)
        .join(Account, Account.id == CarteraSnapshot.account_id)
        .where(
            Account.user_id == user_id,
            Account.account_type == AccountType.broker,
            CarteraSnapshot.period_month == month,
        )
    )
    total_ars = Decimal("0")
    for snap in snapshots:
        total_ars += sum(
            Decimal(str(p.get("valor_base_ars", 0) or 0)) for p in (snap.posiciones or [])
        )
    return float(total_ars / mep) if total_ars else None


async def get_monthly_series(
    db: AsyncSession, user_id, anchor: date, count: int = 6
) -> list[dict]:
    """
    Serie mensual (más reciente primero → oldest last se revierte al final) para
    el gráfico compuesto y la tabla de flujo: hasta `count` meses terminando en
    `anchor`. Cada punto trae flujo (en ARS, vivo desde transacciones) y, cuando
    hay dato disponible, patrimonio y cartera en USD para graficar todo junto.
    """
    months: list[date] = []
    m = anchor
    for _ in range(count):
        months.append(m)
        m = _prev_month(m)
    months.reverse()  # oldest → newest

    points: list[dict] = []
    for month in months:
        flujo = await get_flujo_del_mes(db, user_id, month)
        mep = await _get_mep_for_month(db, month)

        resultado_usd = (
            float(Decimal(str(flujo["resultado_ars"])) / mep) if mep else None
        )
        gasto_usd = (
            float(abs(Decimal(str(flujo["egresos_ars"]))) / mep) if mep else None
        )
        patrimonio_usd = await _get_patrimonio_for_series(db, user_id, month, anchor)
        cartera_usd = await _get_cartera_usd_for_month(db, user_id, month, mep)

        points.append(
            {
                "month": month.strftime("%Y-%m"),
                "ingresos_ars": flujo["ingresos_ars"],
                "egresos_ars": flujo["egresos_ars"],
                "resultado_ars": flujo["resultado_ars"],
                "resultado_usd": resultado_usd,
                "gasto_usd": gasto_usd,
                "patrimonio_usd": patrimonio_usd,
                "cartera_usd": cartera_usd,
            }
        )
    return points


def generate_insights(
    current_month: MonthSummary,
    previous_month: MonthSummary | None,
    current_flujo: dict[str, float] | None = None,
    previous_flujo: dict[str, float] | None = None,
) -> list[str]:
    """
    Insights de alto nivel (mes vs. mes anterior) — resultado y gasto total,
    no desglosados por categoría. Un insight por categoría con 13+ categorías
    resultaba en una lista larga y poco accionable; esto prioriza lo grande.
    """
    insights = []

    if current_flujo and previous_flujo:
        prev_resultado = previous_flujo.get("resultado_ars", 0)
        if prev_resultado:
            diff_pct = ((current_flujo["resultado_ars"] - prev_resultado) / abs(prev_resultado)) * 100
            if abs(diff_pct) >= 5:
                direction = "mayor" if diff_pct > 0 else "menor"
                insights.append(
                    f"El resultado de este mes fue un {abs(diff_pct):.0f}% {direction} que el mes pasado"
                )

        prev_egresos = abs(previous_flujo.get("egresos_ars", 0))
        if prev_egresos:
            current_egresos = abs(current_flujo.get("egresos_ars", 0))
            diff_pct = ((current_egresos - prev_egresos) / prev_egresos) * 100
            if abs(diff_pct) >= 5:
                direction = "aumentaron" if diff_pct > 0 else "bajaron"
                insights.append(f"Tus gastos {direction} un {abs(diff_pct):.0f}% respecto al mes pasado")

    portfolio_change = current_month.total_usd - (
        previous_month.total_usd if previous_month else Decimal("0")
    )
    if portfolio_change != 0:
        direction = "subio" if portfolio_change > 0 else "bajo"
        insights.append(f"Tu patrimonio {direction} USD {abs(portfolio_change):,.0f} este mes")

    return insights


def generate_snapshot_insights(snapshot: FinancialSnapshot | None) -> list[str]:
    """
    Templates en texto sobre los módulos de la skill, SIN llamar a Claude.
    Solo agrega insights para los módulos que efectivamente se hayan calculado.
    """
    insights: list[str] = []
    if snapshot is None:
        return insights

    if snapshot.proyeccion:
        insights += _proyeccion_insights(snapshot.proyeccion)

    if snapshot.tablero_general and snapshot.tablero_general.get("alertas"):
        insights += [_translate_alert(a) for a in snapshot.tablero_general["alertas"]]

    return insights


def _cartera_insights(cartera: dict) -> list[str]:
    """
    Nivel 3: resultado realizado por ventas/vencimientos. Nivel 2: rendimientos netos
    cobrados (dividendos/intereses). Ninguno de los dos existe en Nivel 1 — quedan
    ausentes (no en 0) si el mes no alcanzó ese nivel, siguiendo el principio central
    del Módulo 4 (ver 04_cuenta_comitente.md).
    """
    insights = []
    posiciones = cartera.get("posiciones", [])

    resultado_realizado = sum(
        Decimal(str(p.get("resultado_realizado_ars", 0) or 0)) for p in posiciones
    )
    if resultado_realizado > 0:
        insights.append(f"Resultado realizado en tu cartera: +${resultado_realizado:,.0f} en el período")
    elif resultado_realizado < 0:
        insights.append(f"Resultado realizado en tu cartera: -${abs(resultado_realizado):,.0f} en el período")

    rendimientos_netos = cartera.get("rendimientos_netos_ars")
    if rendimientos_netos:
        insights.append(
            f"Cobraste ${Decimal(str(rendimientos_netos)):,.0f} en rendimientos netos de tu cartera este período"
        )

    return insights


def _cartera_alerts(cartera: dict, previous_cartera: dict | None) -> list[str]:
    """
    Alertas de concentración y caída de cartera, calculadas de forma determinística sobre
    pct_cartera/valor_base_ars ya guardados — nunca redactadas por el LLM (ver reglas en
    _output_contract.md). "Sin movimientos 3 meses" y "doble representación FCI/billetera"
    quedan fuera de esta fase: requieren cruzar 3+ meses de historial y otras cuentas del
    usuario respectivamente — se abordan junto con la página Cartera.
    """
    alerts: list[str] = []
    posiciones = cartera.get("posiciones", [])

    for pos in posiciones:
        pct = pos.get("pct_cartera") or 0
        if pct > 0.40:
            alerts.append(
                f"🟡 CONCENTRACIÓN: {pos.get('instrumento', '?')} = {pct * 100:.0f}% de la cartera"
            )

    if previous_cartera:
        total = sum(Decimal(str(p.get("valor_base_ars", 0) or 0)) for p in posiciones)
        prev_posiciones = previous_cartera.get("posiciones", [])
        prev_total = sum(Decimal(str(p.get("valor_base_ars", 0) or 0)) for p in prev_posiciones)
        if prev_total > 0:
            delta_pct = (total - prev_total) / prev_total
            if delta_pct <= Decimal("-0.20"):
                alerts.append(
                    f"🔴 CAÍDA SEVERA: la cartera perdió {abs(delta_pct) * 100:.0f}% "
                    f"(${abs(total - prev_total):,.0f}) en el mes"
                )
            elif delta_pct <= Decimal("-0.10"):
                alerts.append(
                    f"🔴 CAÍDA DE CARTERA: la cartera perdió {abs(delta_pct) * 100:.0f}% "
                    f"(${abs(total - prev_total):,.0f}) en el mes"
                )

    return alerts


def _proyeccion_insights(proyeccion: dict) -> list[str]:
    insights = []
    banda_media = proyeccion.get("banda_media")
    if banda_media is not None:
        insights.append(
            f"Proyectamos un patrimonio liquido de ${banda_media:,.0f} dentro de 3 meses"
        )
    return insights


def _translate_alert(alert) -> str:
    if isinstance(alert, dict):
        tipo = alert.get("tipo", "")
        mensaje = alert.get("mensaje") or alert.get("message") or alert.get("texto") or ""
        return f"{tipo} {mensaje}".strip() if tipo else mensaje
    return str(alert)


def _cartera_total_ars(posiciones: list[dict] | None) -> Decimal:
    return sum(Decimal(str(p.get("valor_base_ars", 0) or 0)) for p in (posiciones or []))


def _cartera_composicion_por_tipo(posiciones: list[dict] | None) -> dict[str, float]:
    total = _cartera_total_ars(posiciones)
    composicion: dict[str, float] = {}
    if not total:
        return composicion
    for pos in posiciones or []:
        tipo = pos.get("tipo", "otro")
        valor = Decimal(str(pos.get("valor_base_ars", 0) or 0))
        composicion[tipo] = composicion.get(tipo, 0.0) + float(valor / total)
    return composicion


async def get_account_cartera(
    db: AsyncSession, account_id, months: int = 6, period: date | None = None
) -> dict | None:
    """
    Historia de cartera de UNA cuenta comitente puntual (nunca agregada con otras
    cuentas — cada una tiene su propia tabla de posiciones y evolución). Devuelve None
    si todavía no se procesó ningún archivo para esta cuenta (hasta `period`, si se pasa).

    `period`, si se pasa, ancla la ventana a meses <= period (para "qué se sabía en
    Mes a mes al mirar ese mes puntual" o para navegar la página Cartera a un mes
    específico) — sin él, ancla al mes más reciente real.
    """
    query = select(CarteraSnapshot).where(CarteraSnapshot.account_id == account_id)
    if period is not None:
        query = query.where(CarteraSnapshot.period_month <= period)
    snapshots = list(
        await db.scalars(query.order_by(CarteraSnapshot.period_month.desc()).limit(months))
    )
    if not snapshots:
        return None
    snapshots.reverse()  # oldest -> newest, para poder calcular Δ contra el mes anterior

    evolucion = []
    prev_total: Decimal | None = None
    for snap in snapshots:
        total = _cartera_total_ars(snap.posiciones)
        delta_ars = float(total - prev_total) if prev_total is not None else None
        delta_pct = float((total - prev_total) / prev_total) if prev_total else None
        evolucion.append(
            {
                "month": snap.period_month.strftime("%Y-%m"),
                "nivel_detectado": snap.nivel_detectado,
                "valor_base_ars": float(total),
                "delta_ars": delta_ars,
                "delta_pct": delta_pct,
                "composicion_por_tipo": _cartera_composicion_por_tipo(snap.posiciones),
            }
        )
        prev_total = total

    latest = snapshots[-1]
    latest_cartera = {
        "posiciones": latest.posiciones,
        "rendimientos_netos_ars": latest.rendimientos_netos_ars,
    }
    previous_cartera = {"posiciones": snapshots[-2].posiciones} if len(snapshots) >= 2 else None

    return {
        "month": latest.period_month.strftime("%Y-%m"),
        "nivel_detectado": latest.nivel_detectado,
        "posiciones": latest.posiciones,
        "rendimientos_netos_ars": latest.rendimientos_netos_ars,
        "retenciones_ars": latest.retenciones_ars,
        "delta_cartera_mes": latest.delta_cartera_mes,
        "evolucion": evolucion,
        "composicion_por_tipo": evolucion[-1]["composicion_por_tipo"],
        "alertas": _cartera_alerts(latest_cartera, previous_cartera),
        "insights": _cartera_insights(latest_cartera),
    }
