"""
Seed script: creates testUser in Cognito + DB and loads realistic fake data.

Usage (from Vault-backend root, with .venv active):
    python scripts/seed_test_user.py

To reset and re-run:
    python scripts/seed_test_user.py --reset

What it does:
  1. Creates testuser@vault.local in Cognito via admin API (no email verification,
     no MFA, permanent password) — bypasses the normal registration flow entirely.
  2. Inserts the user in the DB using the Cognito sub.
  3. Creates 4 accounts: efectivo USD, BBVA checking ARS, Bruker broker USD, Lemon crypto USD.
  4. Inserts TC MEP for the last 13 months.
  5. Inserts ~8 months of transactions across accounts (ARS and USD).

Login in the app:
    Email:    testuser@vault.local
    Password: testUser1!
    (No TOTP — MFA is not configured for this user)
"""

import argparse
import asyncio
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, ".")

from app.config import settings
from app.models.account import Account
from app.models.enums import AccountType, CurrencyType, MepSource
from app.models.exchange_rate import ExchangeRate
from app.models.transaction import Transaction
from app.models.user import User

TEST_EMAIL = "testuser@vaultapp.dev"
TEST_NAME = "Test User"
TEST_PASSWORD = "testUser1!"

# Realistic MEP rates for the last 13 months (approximate)
MEP_RATES: list[tuple[date, Decimal]] = [
    (date(2025, 6, 1), Decimal("930.00")),
    (date(2025, 7, 1), Decimal("955.00")),
    (date(2025, 8, 1), Decimal("980.00")),
    (date(2025, 9, 1), Decimal("1005.00")),
    (date(2025, 10, 1), Decimal("1030.00")),
    (date(2025, 11, 1), Decimal("1060.00")),
    (date(2025, 12, 1), Decimal("1085.00")),
    (date(2026, 1, 1), Decimal("1110.00")),
    (date(2026, 2, 1), Decimal("1130.00")),
    (date(2026, 3, 1), Decimal("1155.00")),
    (date(2026, 4, 1), Decimal("1170.00")),
    (date(2026, 5, 1), Decimal("1190.00")),
    (date(2026, 6, 1), Decimal("1210.00")),
]


def _first_day(year: int, month: int) -> date:
    return date(year, month, 1)


def _dates_in_month(year: int, month: int, count: int) -> list[date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    days = (end - start).days + 1
    step = max(1, days // count)
    return [start + timedelta(days=i * step) for i in range(count)]


# (description, amount_ars, category)  — negative = egreso, positive = ingreso
MONTHLY_ARS_TRANSACTIONS: list[tuple[str, int, str]] = [
    ("Jumbo supermercado", -45000, "Supermercado"),
    ("Día supermercado", -18000, "Supermercado"),
    ("Mercado libre compra", -12000, "Varios"),
    ("Rappi delivery", -4500, "Restaurantes"),
    ("PedidosYa delivery", -3800, "Restaurantes"),
    ("El Federal restaurante", -8500, "Restaurantes"),
    ("Sube carga", -3000, "Transporte"),
    ("Cabify", -2200, "Transporte"),
    ("Netflix", -3500, "Entretenimiento"),
    ("Spotify", -1200, "Entretenimiento"),
    ("Farmacity", -4200, "Salud"),
    ("Expensas", -85000, "Servicios"),
    ("Edesur electricidad", -9500, "Servicios"),
    ("Metrogas", -6800, "Servicios"),
    ("Personal celular", -7200, "Servicios"),
    ("Sueldo", 850000, "Ingreso"),
    ("Bono trimestral", 120000, "Ingreso"),
]


def create_cognito_user(cognito) -> str:
    """
    Creates the user via client-side sign_up (no IAM admin permissions needed).
    Then tries admin_confirm_sign_up + admin_set_user_password — these require
    cognito-idp:AdminConfirmSignUp and cognito-idp:AdminSetUserPassword on vault-dev.
    If they fail, instructions are printed and the script exits.
    """
    sub: str | None = None

    # 1. sign_up — no IAM required
    try:
        resp = cognito.sign_up(
            ClientId=settings.cognito_client_id,
            Username=TEST_EMAIL,
            Password=TEST_PASSWORD,
            UserAttributes=[
                {"Name": "email", "Value": TEST_EMAIL},
                {"Name": "name", "Value": TEST_NAME},
            ],
        )
        sub = resp["UserSub"]
        print(f"  Cognito user registered (sub={sub[:8]}...)")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UsernameExistsException":
            print("  Cognito user already exists — attempting to get sub via auth...")
            # Try initiating auth to get the sub from the token
            try:
                auth_resp = cognito.initiate_auth(
                    ClientId=settings.cognito_client_id,
                    AuthFlow="USER_PASSWORD_AUTH",
                    AuthParameters={"USERNAME": TEST_EMAIL, "PASSWORD": TEST_PASSWORD},
                )
                id_token = auth_resp.get("AuthenticationResult", {}).get("IdToken")
                if id_token:
                    import base64
                    import json

                    payload = id_token.split(".")[1]
                    payload += "=" * (4 - len(payload) % 4)
                    claims = json.loads(base64.b64decode(payload))
                    sub = claims.get("sub")
                    print(f"  Retrieved sub from existing login (sub={sub[:8] if sub else '?'}...)")
            except ClientError:
                pass
            if not sub:
                print("\n  ✗ User exists in Cognito but couldn't retrieve sub.")
                print("    Run with --reset to delete and recreate.")
                sys.exit(1)
            return sub
        raise

    # 2. admin_confirm_sign_up — needs IAM permission cognito-idp:AdminConfirmSignUp
    try:
        cognito.admin_confirm_sign_up(
            UserPoolId=settings.cognito_user_pool_id,
            Username=TEST_EMAIL,
        )
        print("  Email confirmed via admin API")
    except ClientError as e:
        if "AccessDeniedException" in str(e) or "NotAuthorizedException" in str(e):
            print("\n  ✗ Falta permiso IAM: cognito-idp:AdminConfirmSignUp en vault-dev")
            print("    En AWS Console → IAM → Users → vault-dev → Add permissions:")
            print("    Agregar política gestionada: AmazonCognitoPowerUser")
            print("    Luego volver a correr este script.")
            sys.exit(1)
        raise

    # 3. admin_set_user_password — sets permanent password (no FORCE_CHANGE_PASSWORD state)
    try:
        cognito.admin_set_user_password(
            UserPoolId=settings.cognito_user_pool_id,
            Username=TEST_EMAIL,
            Password=TEST_PASSWORD,
            Permanent=True,
        )
        print("  Password set as permanent")
    except ClientError as e:
        if "AccessDeniedException" in str(e) or "NotAuthorizedException" in str(e):
            print("\n  ✗ Falta permiso IAM: cognito-idp:AdminSetUserPassword en vault-dev")
            print("    En AWS Console → IAM → Users → vault-dev → Add permissions:")
            print("    Agregar política gestionada: AmazonCognitoPowerUser")
            sys.exit(1)
        raise

    print(f"  Cognito user ready (sub={sub[:8]}...)")
    return sub


def delete_cognito_user(cognito) -> None:
    try:
        cognito.admin_delete_user(UserPoolId=settings.cognito_user_pool_id, Username=TEST_EMAIL)
        print("  Cognito user deleted")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UserNotFoundException":
            pass
        elif "AccessDeniedException" in str(e):
            print("  ⚠ No se pudo eliminar de Cognito (sin permiso AdminDeleteUser) — omitiendo")
        else:
            raise


async def reset_db_user(db: AsyncSession, email: str) -> None:
    user = await db.scalar(select(User).where(User.email == email))
    if user:
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()
        print("  DB user and all related data deleted (cascade)")


async def seed(db: AsyncSession, cognito_sub: str) -> None:
    # ── User ──────────────────────────────────────────────────────────────────
    existing = await db.scalar(select(User).where(User.email == TEST_EMAIL))
    if existing:
        print("  DB user already exists — skipping seed (run with --reset to reload)")
        return

    user = User(
        email=TEST_EMAIL,
        name=TEST_NAME,
        cognito_sub=cognito_sub,
        base_currency=CurrencyType.USD,
    )
    db.add(user)
    await db.flush()

    # ── Accounts ──────────────────────────────────────────────────────────────
    acct_efectivo = Account(
        user_id=user.id,
        name="Efectivo USD",
        account_type=AccountType.cash,
        institution=None,
        currency=CurrencyType.USD,
        current_balance=Decimal("2150.00"),
    )
    acct_bbva = Account(
        user_id=user.id,
        name="BBVA Cuenta corriente",
        account_type=AccountType.checking_ars,
        institution="BBVA",
        currency=CurrencyType.ARS,
        current_balance=Decimal("485000.00"),
    )
    acct_broker = Account(
        user_id=user.id,
        name="Bruker Inversiones",
        account_type=AccountType.broker,
        institution="Bruker",
        currency=CurrencyType.USD,
        current_balance=Decimal("8300.00"),
    )
    acct_crypto = Account(
        user_id=user.id,
        name="Lemon Crypto",
        account_type=AccountType.crypto,
        institution="Lemon",
        currency=CurrencyType.USD,
        current_balance=Decimal("1200.00"),
    )
    db.add_all([acct_efectivo, acct_bbva, acct_broker, acct_crypto])
    await db.flush()
    print(f"  Created 4 accounts for user {user.id}")

    # ── Exchange rates ─────────────────────────────────────────────────────────
    for period, rate in MEP_RATES:
        existing_rate = await db.scalar(
            select(ExchangeRate).where(ExchangeRate.period_month == period)
        )
        if not existing_rate:
            db.add(ExchangeRate(period_month=period, mep_rate=rate, source=MepSource.manual))
    await db.flush()
    print(f"  Inserted {len(MEP_RATES)} TC MEP rates")

    # ── Transactions (ARS — last 8 months on BBVA) ────────────────────────────
    today = date.today()
    tx_count = 0
    for months_back in range(7, -1, -1):
        # compute year/month
        month = today.month - months_back
        year = today.year
        while month <= 0:
            month += 12
            year -= 1

        # shuffle transactions slightly for variety
        txs = list(MONTHLY_ARS_TRANSACTIONS)
        random.shuffle(txs)
        dates = _dates_in_month(year, month, len(txs))

        for i, (desc, amount, category) in enumerate(txs):
            # slight random variation ±8%
            factor = Decimal(str(1 + random.uniform(-0.08, 0.08)))
            signed = Decimal(str(amount)) * factor

            db.add(
                Transaction(
                    user_id=user.id,
                    account_id=acct_bbva.id,
                    upload_id=None,
                    date=dates[i],
                    description=desc,
                    amount_ars=signed.quantize(Decimal("0.01")),
                    amount_usd=None,
                    currency=CurrencyType.ARS,
                    category=category,
                    confidence=Decimal("0.99"),
                    needs_review=False,
                    is_corrected=True,
                )
            )
            tx_count += 1

    # ── A few USD transactions on the broker account ──────────────────────────
    usd_txs = [
        ("Compra CEDEARs Apple", -500, "Inversiones"),
        ("Compra BPAN24", -300, "Inversiones"),
        ("Dividendo Coca-Cola", 85, "Inversiones"),
        ("Comisión Bruker", -12, "Servicios"),
        ("Venta CEDEARs Tesla", 620, "Inversiones"),
    ]
    broker_dates = _dates_in_month(today.year, today.month, len(usd_txs))
    for i, (desc, amount, category) in enumerate(usd_txs):
        db.add(
            Transaction(
                user_id=user.id,
                account_id=acct_broker.id,
                upload_id=None,
                date=broker_dates[i],
                description=desc,
                amount_ars=Decimal("0"),
                amount_usd=Decimal(str(amount)),
                currency=CurrencyType.USD,
                category=category,
                confidence=Decimal("0.99"),
                needs_review=False,
                is_corrected=True,
            )
        )
        tx_count += 1

    await db.commit()
    print(f"  Inserted {tx_count} transactions")
    print()
    print("  ✓ Seed complete")
    print(f"    Email:    {TEST_EMAIL}")
    print(f"    Password: {TEST_PASSWORD}")
    print("    MFA:      not configured — log in directly")


async def main(reset: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    cognito = boto3.client(
        "cognito-idp",
        region_name=settings.cognito_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    print("── Cognito ──────────────────────────────────────")
    if reset:
        delete_cognito_user(cognito)
    cognito_sub = create_cognito_user(cognito)

    print("── Database ─────────────────────────────────────")
    async with session_factory() as db:
        if reset:
            await reset_db_user(db, TEST_EMAIL)
        await seed(db, cognito_sub)

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed testUser into Vault")
    parser.add_argument("--reset", action="store_true", help="Delete existing data and re-seed")
    args = parser.parse_args()
    asyncio.run(main(reset=args.reset))
