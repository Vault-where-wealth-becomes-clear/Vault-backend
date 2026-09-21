import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CurrencyType
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.services import audit_service


async def recalculate_period(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_month: date,
    mep_rate: Decimal,
    actor_user_id: uuid.UUID | None = None,
) -> int:
    """Recalcula el lado derivado de amount_ars/amount_usd usando el TC MEP dado.

    La moneda nativa de cada transaccion (Transaction.currency) es el dato real
    del extracto y nunca se sobreescribe; solo se recalcula el lado convertido,
    para no mezclar pesos y dolares al redeclarar el TC de un periodo.

    Solo afecta el periodo indicado, nunca recalcula retroactivamente otros
    periodos, y solo toca los uploads de `user_id`: sin ese filtro, redeclarar
    el TC de un mes reescribia los montos convertidos de todos los usuarios.

    actor_user_id es quien disparo el recalculo (None = proceso automatico,
    ej. el job diario de MEP). Se deja un renglon en audit_log solo cuando
    de verdad se toco algo, para no llenar la tabla con los no-ops del job
    automatico corriendo sobre usuarios sin uploads ese mes.
    """
    upload_ids = await db.scalars(
        select(Upload.id).where(
            Upload.user_id == user_id,
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
    total_updated = (ars_result.rowcount or 0) + (usd_result.rowcount or 0)

    if total_updated:
        await audit_service.record(
            db,
            user_id=user_id,
            actor_user_id=actor_user_id,
            entity_type="exchange_rate",
            entity_id=None,
            action="transactions_recalculated",
            before=None,
            after={
                "period_month": period_month.isoformat(),
                "mep_rate": float(mep_rate),
                "transactions_updated": total_updated,
            },
        )

    return total_updated
