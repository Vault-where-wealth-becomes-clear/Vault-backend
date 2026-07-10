import uuid
from datetime import date
from decimal import Decimal

from app.models.account import Account
from app.models.enums import AccountType, CurrencyType
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.services.dashboard_service import get_month_summary


async def _make_user(db) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()
    return user.id


async def test_ars_cash_balance_is_converted_via_mep_rate(db):
    user_id = await _make_user(db)
    db.add(
        Account(
            user_id=user_id,
            name="Efectivo pesos",
            account_type=AccountType.cash,
            currency=CurrencyType.ARS,
            current_balance=Decimal("130000.00"),
        )
    )
    db.add(ExchangeRate(period_month=date(2026, 7, 1), mep_rate=Decimal("1300")))
    await db.flush()

    summary = await get_month_summary(db, user_id, date(2026, 7, 1))

    assert summary.total_usd == Decimal("100")


async def test_ars_cash_balance_is_skipped_without_a_declared_rate(db):
    user_id = await _make_user(db)
    db.add(
        Account(
            user_id=user_id,
            name="Efectivo pesos",
            account_type=AccountType.cash,
            currency=CurrencyType.ARS,
            current_balance=Decimal("130000.00"),
        )
    )
    await db.flush()

    # Sin TC declarado para el periodo no se puede convertir de forma segura:
    # el saldo se omite (no se mezcla 1 ARS == 1 USD) en vez de asumir un TC 1:1.
    summary = await get_month_summary(db, user_id, date(2026, 7, 1))

    assert summary.total_usd == Decimal("0")
