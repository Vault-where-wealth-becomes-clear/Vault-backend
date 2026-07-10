from datetime import date
from decimal import Decimal

from sqlalchemy import extract, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CurrencyType
from app.models.transaction import Transaction
from app.models.upload import Upload


async def recalculate_period(db: AsyncSession, period_month: date, mep_rate: Decimal) -> int:
    """Recalcula el lado derivado de amount_ars/amount_usd usando el TC MEP dado.

    La moneda nativa de cada transaccion (Transaction.currency) es el dato real
    del extracto y nunca se sobreescribe; solo se recalcula el lado convertido,
    para no mezclar pesos y dolares al redeclarar el TC de un periodo.

    Solo afecta el periodo indicado, nunca recalcula retroactivamente otros periodos.
    """
    upload_ids = await db.scalars(
        select(Upload.id).where(
            extract("year", Upload.period_month) == period_month.year,
            extract("month", Upload.period_month) == period_month.month,
        )
    )
    upload_ids = list(upload_ids)
    if not upload_ids:
        return 0

    ars_result = await db.execute(
        update(Transaction)
        .where(
            Transaction.upload_id.in_(upload_ids),
            Transaction.currency == CurrencyType.ARS,
        )
        .values(amount_usd=Transaction.amount_ars / mep_rate)
    )
    usd_result = await db.execute(
        update(Transaction)
        .where(
            Transaction.upload_id.in_(upload_ids),
            Transaction.currency == CurrencyType.USD,
        )
        .values(amount_ars=Transaction.amount_usd * mep_rate)
    )
    return (ars_result.rowcount or 0) + (usd_result.rowcount or 0)
