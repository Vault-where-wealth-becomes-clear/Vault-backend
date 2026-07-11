import uuid
from datetime import date
from decimal import Decimal

from app.models.account import Account
from app.models.enums import AccountType, CurrencyType
from app.models.exchange_rate import ExchangeRate
from app.models.transaction import Transaction
from app.models.user import User
from app.services.dashboard_service import get_flujo_del_mes, get_month_summary


async def _make_user(db) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()
    return user.id


async def _make_account(db, user_id, account_type: AccountType) -> uuid.UUID:
    account = Account(
        user_id=user_id,
        name=f"Test {account_type.value}",
        account_type=account_type,
        currency=CurrencyType.ARS,
    )
    db.add(account)
    await db.flush()
    return account.id


async def _add_txn(db, user_id, account_id, amount_ars: str, category: str) -> None:
    db.add(
        Transaction(
            user_id=user_id,
            account_id=account_id,
            date=date(2026, 7, 5),
            description=f"{category} test",
            currency=CurrencyType.ARS,
            amount_ars=Decimal(amount_ars),
            category=category,
            needs_review=False,
        )
    )
    await db.flush()


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


async def test_flujo_del_mes_es_la_variacion_de_cuentas_de_efectivo(db):
    """
    Regresión del bug reportado: "Flujo del mes" tiene que ser la variación real de
    las cuentas de efectivo del usuario — ni un centavo más ni menos — excluyendo
    solo tarjetas de crédito y cuenta comitente por TIPO de cuenta, nunca por
    categoría de transacción. Si alguna vez se vuelve a agregar un filtro de
    categoría acá (ej. para excluir "Pago deuda"), este test se rompe: pagar la
    tarjeta es plata real saliendo de una cuenta de efectivo ese mes y tiene que
    contar, sin importar la categoría que tenga.
    """
    user_id = await _make_user(db)

    checking_id = await _make_account(db, user_id, AccountType.checking_ars)
    credit_card_id = await _make_account(db, user_id, AccountType.credit_card_ars)
    broker_id = await _make_account(db, user_id, AccountType.broker)

    # Cuenta de efectivo: ingreso operativo, gasto, y el pago de la tarjeta —
    # las tres deben contar en el flujo, categoría "no operativa" incluida.
    await _add_txn(db, user_id, checking_id, "80000.00", "Ingreso operativo")
    await _add_txn(db, user_id, checking_id, "-1000.00", "Restaurantes")
    await _add_txn(db, user_id, checking_id, "-50000.00", "Pago deuda")

    # Tarjeta de crédito y cuenta comitente: montos enormes a propósito — si
    # alguna vez se filtran por tipo de cuenta mal, el test los va a delatar.
    await _add_txn(db, user_id, credit_card_id, "-999999.00", "Restaurantes")
    await _add_txn(db, user_id, broker_id, "999999.00", "Rendimiento")

    flujo = await get_flujo_del_mes(db, user_id, date(2026, 7, 1))

    assert flujo["ingresos_ars"] == 80000.0
    assert flujo["egresos_ars"] == -51000.0
    assert flujo["resultado_ars"] == 29000.0
