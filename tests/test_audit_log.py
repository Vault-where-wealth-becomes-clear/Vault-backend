"""Corregir una categoria y recalcular un periodo tienen que dejar rastro en
audit_log: quien lo hizo (o que fue un proceso automatico), y el valor antes/
despues. El job automatico de MEP no puede generar ruido en usuarios sin
uploads ese mes."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.enums import AccountType, CurrencyType
from app.models.exchange_rate import ExchangeRate
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
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


async def test_correcting_a_category_leaves_an_audit_trail(client, db):
    from app.main import app
    from app.middleware.auth import get_current_user

    user_id, txn_id = await _make_user_with_ars_transaction(db, "100000.00")
    txn = await db.get(Transaction, txn_id)
    txn.category = "Comida"
    await db.flush()

    fake_user = await db.get(User, user_id)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        resp = await client.patch(f"/transactions/{txn_id}", json={"category": "Transporte"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200

    entry = await db.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == txn_id, AuditLog.action == "category_corrected"
        )
    )
    assert entry is not None
    assert entry.actor_user_id == user_id
    assert entry.before == {"category": "Comida"}
    assert entry.after == {"category": "Transporte"}


async def test_recalculate_period_leaves_an_audit_trail_with_the_triggering_actor(db):
    ana_id, _ = await _make_user_with_ars_transaction(db, "100000.00")
    db.add(ExchangeRate(user_id=ana_id, period_month=_PERIODO, mep_rate=Decimal("2000")))
    await db.flush()

    updated = await recalculate_period(db, ana_id, _PERIODO, Decimal("2000"), actor_user_id=ana_id)
    assert updated == 1

    entry = await db.scalar(
        select(AuditLog).where(
            AuditLog.user_id == ana_id, AuditLog.action == "transactions_recalculated"
        )
    )
    assert entry is not None
    assert entry.actor_user_id == ana_id
    assert entry.after["transactions_updated"] == 1
    assert entry.after["mep_rate"] == 2000.0


async def test_recalculate_period_from_an_automated_job_has_no_actor(db):
    ana_id, _ = await _make_user_with_ars_transaction(db, "100000.00")
    await db.flush()

    updated = await recalculate_period(db, ana_id, _PERIODO, Decimal("1500"))
    assert updated == 1

    entry = await db.scalar(
        select(AuditLog).where(
            AuditLog.user_id == ana_id, AuditLog.action == "transactions_recalculated"
        )
    )
    assert entry.actor_user_id is None, "un proceso automatico no tiene un usuario actor"


async def test_recalculate_period_does_not_log_when_nothing_was_updated(db):
    ana_id, _ = await _make_user_with_ars_transaction(db, "100000.00")
    await db.flush()

    otro_periodo = date(2026, 8, 1)
    updated = await recalculate_period(db, ana_id, otro_periodo, Decimal("1500"))
    assert updated == 0

    entry = await db.scalar(
        select(AuditLog).where(
            AuditLog.user_id == ana_id, AuditLog.action == "transactions_recalculated"
        )
    )
    assert entry is None, "un recalculo que no toco nada no deberia ensuciar el audit log"
