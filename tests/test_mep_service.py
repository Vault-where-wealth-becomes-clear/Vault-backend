import uuid
from datetime import date
from decimal import Decimal

from app.models.account import Account
from app.models.enums import AccountType, CurrencyType
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.mep_service import recalculate_period


async def _make_user_account_upload(db, account_currency: CurrencyType) -> tuple:
    user = User(email=f"{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()

    account = Account(
        user_id=user.id,
        name="Test account",
        account_type=(
            AccountType.checking_usd
            if account_currency == CurrencyType.USD
            else AccountType.checking_ars
        ),
        currency=account_currency,
    )
    db.add(account)
    await db.flush()

    upload = Upload(
        user_id=user.id,
        account_id=account.id,
        s3_key_pdf="test.pdf",
        period_month=date(2026, 7, 1),
    )
    db.add(upload)
    await db.flush()

    return user.id, account.id, upload.id


async def test_recalculate_period_does_not_corrupt_usd_native_transactions(db):
    user_id, account_id, upload_id = await _make_user_account_upload(db, CurrencyType.USD)

    txn = Transaction(
        user_id=user_id,
        account_id=account_id,
        upload_id=upload_id,
        date=date(2026, 7, 5),
        description="Compra en dolares",
        currency=CurrencyType.USD,
        amount_usd=Decimal("100.0000"),
        amount_ars=Decimal("100.0000") * Decimal("1000"),  # ingresado con TC viejo (1000)
    )
    db.add(txn)
    await db.flush()

    await recalculate_period(db, date(2026, 7, 1), Decimal("1300"))
    await db.refresh(txn)

    # El monto en USD es el dato real del extracto: no debe cambiar al redeclarar el TC.
    assert txn.amount_usd == Decimal("100.0000")
    # El equivalente en ARS si debe recalcularse con el nuevo TC.
    assert txn.amount_ars == Decimal("130000.00")


async def test_recalculate_period_updates_usd_for_ars_native_transactions(db):
    user_id, account_id, upload_id = await _make_user_account_upload(db, CurrencyType.ARS)

    txn = Transaction(
        user_id=user_id,
        account_id=account_id,
        upload_id=upload_id,
        date=date(2026, 7, 5),
        description="Compra en pesos",
        currency=CurrencyType.ARS,
        amount_ars=Decimal("130000.00"),
        amount_usd=Decimal("100.0000"),  # ingresado con TC viejo (1300)
    )
    db.add(txn)
    await db.flush()

    await recalculate_period(db, date(2026, 7, 1), Decimal("1000"))
    await db.refresh(txn)

    # El monto en ARS es el dato real del extracto: no debe cambiar al redeclarar el TC.
    assert txn.amount_ars == Decimal("130000.00")
    # El equivalente en USD si debe recalcularse con el nuevo TC.
    assert txn.amount_usd == Decimal("130.0000")
