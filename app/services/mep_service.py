from datetime import date
from decimal import Decimal

from sqlalchemy import extract, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.upload import Upload


async def recalculate_period(db: AsyncSession, period_month: date, mep_rate: Decimal) -> int:
    """Recalcula amount_usd de las transacciones del periodo usando el TC MEP dado.

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

    result = await db.execute(
        update(Transaction)
        .where(Transaction.upload_id.in_(upload_ids))
        .values(amount_usd=Transaction.amount_ars / mep_rate)
    )
    return result.rowcount or 0
