"""El TC MEP vivia en una tabla global sin dueño, pero se escribe desde el
flujo normal de cada usuario. Redeclarar el TC de un mes reescribia los montos
convertidos de todos los usuarios a la vez."""

import uuid
from datetime import date
from decimal import Decimal

from app.models.account import Account
from app.models.enums import AccountType, CurrencyType
from app.models.exchange_rate import ExchangeRate
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.dashboard_service import _get_mep_for_month
from app.services.mep_service import recalculate_period

_PERIODO = date(2026, 7, 1)


async def _make_user_with_ars_transaction(db, monto_ars: str) -> tuple[uuid.UUID, uuid.UUID]:
    user = User(email=f"{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()

    account = Account(
        user_id=user.id,
        name="Caja de ahorro",
        account_type=AccountType.checking_ars,
        currency=CurrencyType.ARS,
    )
    db.add(account)
    await db.flush()

    upload = Upload(
        user_id=user.id,
        account_id=account.id,
        s3_key_pdf=f"{user.id}/extracto.pdf",
        period_month=_PERIODO,
    )
    db.add(upload)
    await db.flush()

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        upload_id=upload.id,
        date=date(2026, 7, 10),
        description="Sueldo",
        amount_ars=Decimal(monto_ars),
        amount_usd=Decimal("100.0000"),
        currency=CurrencyType.ARS,
        needs_review=False,
    )
    db.add(txn)
    await db.flush()
    return user.id, txn.id


async def test_recalculating_a_period_does_not_touch_another_users_transactions(db):
    ana_id, txn_ana = await _make_user_with_ars_transaction(db, "100000.00")
    beto_id, txn_beto = await _make_user_with_ars_transaction(db, "100000.00")

    db.add(ExchangeRate(user_id=ana_id, period_month=_PERIODO, mep_rate=Decimal("2000")))
    await db.flush()

    actualizadas = await recalculate_period(db, ana_id, _PERIODO, Decimal("2000"))

    assert actualizadas == 1, "solo la transaccion de Ana entra en el recalculo"
    assert (await db.get(Transaction, txn_ana)).amount_usd == Decimal("50.0000")
    assert (await db.get(Transaction, txn_beto)).amount_usd == Decimal(
        "100.0000"
    ), "el TC declarado por Ana no puede mover los montos convertidos de Beto"


async def test_a_users_rate_is_not_visible_to_another_user(db):
    ana_id, _ = await _make_user_with_ars_transaction(db, "100000.00")
    beto_id, _ = await _make_user_with_ars_transaction(db, "100000.00")

    db.add(ExchangeRate(user_id=ana_id, period_month=_PERIODO, mep_rate=Decimal("2000")))
    await db.flush()

    assert await _get_mep_for_month(db, ana_id, _PERIODO) == Decimal("2000")
    assert (
        await _get_mep_for_month(db, beto_id, _PERIODO) is None
    ), "Beto no declaro TC: el dashboard no puede tomar prestado el de Ana"


async def test_the_same_period_can_hold_one_rate_per_user(db):
    ana_id, _ = await _make_user_with_ars_transaction(db, "100000.00")
    beto_id, _ = await _make_user_with_ars_transaction(db, "100000.00")

    db.add(ExchangeRate(user_id=ana_id, period_month=_PERIODO, mep_rate=Decimal("2000")))
    db.add(ExchangeRate(user_id=beto_id, period_month=_PERIODO, mep_rate=Decimal("1500")))
    await db.flush()

    assert await _get_mep_for_month(db, ana_id, _PERIODO) == Decimal("2000")
    assert await _get_mep_for_month(db, beto_id, _PERIODO) == Decimal("1500")
