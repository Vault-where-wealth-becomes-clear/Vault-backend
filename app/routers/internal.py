"""Endpoints llamados por procesos automáticos (crons), no por usuarios finales.

Autenticación por secreto compartido en un header, no por JWT de usuario —
quien llama es GitHub Actions, no una persona logueada.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.enums import MepSource
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.services.mep_ingestion import MepFetchError, current_period_month, fetch_mep_quote
from app.services.mep_service import recalculate_period

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_internal_secret(x_internal_secret: str = Header(default="")) -> None:
    if not settings.internal_sync_secret or x_internal_secret != settings.internal_sync_secret:
        raise HTTPException(status_code=401, detail="Secreto inválido o no configurado")


@router.post("/exchange-rates/sync-mep", dependencies=[Depends(verify_internal_secret)])
async def sync_mep(db: AsyncSession = Depends(get_db)):
    """Carga el TC MEP del período en curso para cada usuario que no lo haya
    declarado a mano, y recalcula sus transacciones de ese período.

    No toca filas con source=manual: mientras la carga manual siga
    existiendo (ver issue de remoción futura), esta sincronización nunca
    pisa lo que un usuario cargó explícitamente.
    """
    try:
        quote = await fetch_mep_quote()
    except MepFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    period = current_period_month()
    sell_rate = Decimal(str(quote.sell_rate))
    buy_rate = Decimal(str(quote.buy_rate))

    user_ids = (await db.scalars(select(User.id))).all()
    created = updated = skipped_manual = 0
    transactions_recalculated = 0

    for user_id in user_ids:
        rate = await db.scalar(
            select(ExchangeRate).where(
                ExchangeRate.user_id == user_id,
                ExchangeRate.period_month == period,
            )
        )
        if rate is not None and rate.source == MepSource.manual:
            skipped_manual += 1
            continue

        if rate is None:
            db.add(
                ExchangeRate(
                    user_id=user_id,
                    period_month=period,
                    mep_rate=sell_rate,
                    buy_rate=buy_rate,
                    source=MepSource.api,
                )
            )
            created += 1
        else:
            rate.mep_rate = sell_rate
            rate.buy_rate = buy_rate
            updated += 1

        await db.flush()
        transactions_recalculated += await recalculate_period(db, user_id, period, sell_rate)

    return {
        "period_month": period.isoformat(),
        "sell_rate": float(sell_rate),
        "buy_rate": float(buy_rate),
        "quote_source": quote.source,
        "users_created": created,
        "users_updated": updated,
        "users_skipped_manual": skipped_manual,
        "transactions_recalculated": transactions_recalculated,
    }
