"""Ningun usuario puede leer ni modificar recursos de otro.

Los filtros por `current_user.id` estan en su lugar en todos los routers; esta
suite existe para que sigan estandolo. Un chequeo de ownership se pierde en un
refactor sin que nada falle, y en un producto financiero eso no se nota hasta
que alguien ve el dinero de otro.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.aws.s3 import get_s3
from app.main import app
from app.middleware.auth import get_current_user
from app.models.account import Account
from app.models.enums import AccountType, CurrencyType, UploadStatus
from app.models.installment import Installment
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User


class _FakeS3:
    """Captura lo que la app le pide firmar, sin hablar con AWS."""

    def __init__(self) -> None:
        self.bucket = "test-bucket"
        self.client = self
        self.presigned: list[tuple[str, int]] = []

    def put_object(self, **kwargs) -> None:
        pass

    async def generate_presigned_url(self, key: str, content_type: str, expires_in: int = 300):
        self.presigned.append((key, expires_in))
        return f"https://s3.test/{key}"

    async def generate_presigned_get_url(self, key: str, expires_in: int = 900) -> str:
        self.presigned.append((key, expires_in))
        return f"https://s3.test/{key}"


@pytest.fixture
def fake_s3():
    s3 = _FakeS3()
    app.dependency_overrides[get_s3] = lambda: s3
    yield s3
    app.dependency_overrides.pop(get_s3, None)


@pytest.fixture
def act_as():
    def _act_as(user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    yield _act_as
    app.dependency_overrides.pop(get_current_user, None)


async def _make_user(db, nombre: str) -> User:
    user = User(email=f"{nombre}-{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()
    return user


async def _make_full_dataset(db, user: User) -> dict:
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
        s3_key_pdf=f"uploads/{user.id}/2026-07/extracto.pdf",
        period_month=date(2026, 7, 1),
        status=UploadStatus.done,
    )
    db.add(upload)
    await db.flush()

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        upload_id=upload.id,
        date=date(2026, 7, 10),
        description="Heladera en 12 cuotas",
        amount_ars=Decimal("-120000.00"),
        amount_usd=Decimal("-100.0000"),
        currency=CurrencyType.ARS,
        needs_review=False,
    )
    db.add(txn)
    await db.flush()

    db.add(
        Installment(
            transaction_id=txn.id,
            user_id=user.id,
            description="Heladera",
            current_installment=1,
            total_installments=12,
            amount_per_installment=Decimal("10000.00"),
            currency=CurrencyType.ARS,
        )
    )
    await db.flush()

    return {"account": account, "upload": upload, "transaction": txn}


async def test_another_users_upload_status_is_not_readable(client, db, act_as):
    ana = await _make_user(db, "ana")
    beto = await _make_user(db, "beto")
    datos = await _make_full_dataset(db, ana)

    act_as(beto)
    response = await client.get(f"/uploads/{datos['upload'].id}/status")

    assert response.status_code == 404


async def test_filtering_transactions_by_another_users_upload_returns_nothing(client, db, act_as):
    """El filtro `upload_id` es del usuario que consulta: pasar el upload de
    otro no puede convertirse en una via para leer sus movimientos."""
    ana = await _make_user(db, "ana")
    beto = await _make_user(db, "beto")
    datos = await _make_full_dataset(db, ana)

    act_as(beto)
    response = await client.get("/transactions", params={"upload_id": str(datos["upload"].id)})

    assert response.status_code == 200
    assert response.json() == []


async def test_another_users_transaction_cannot_be_patched(client, db, act_as):
    ana = await _make_user(db, "ana")
    beto = await _make_user(db, "beto")
    datos = await _make_full_dataset(db, ana)

    act_as(beto)
    response = await client.patch(
        f"/transactions/{datos['transaction'].id}", json={"category": "Servicios"}
    )

    assert response.status_code == 404
    await db.refresh(datos["transaction"])
    assert datos["transaction"].category is None, "la categoria de Ana no se toca"


async def test_installments_only_lists_your_own(client, db, act_as):
    ana = await _make_user(db, "ana")
    beto = await _make_user(db, "beto")
    await _make_full_dataset(db, ana)

    act_as(beto)
    assert (await client.get("/installments")).json() == []

    act_as(ana)
    propias = (await client.get("/installments")).json()
    assert len(propias) == 1
    assert propias[0]["description"] == "Heladera"


async def test_full_dashboard_does_not_leak_another_users_snapshot(client, db, act_as):
    ana = await _make_user(db, "ana")
    beto = await _make_user(db, "beto")
    await _make_full_dataset(db, ana)

    act_as(beto)
    response = await client.get("/dashboard/full")

    assert response.status_code == 200
    body = response.json()
    assert body["flujo_mensual"] is None
    assert body["tablero_general"] is None


async def test_export_only_contains_your_own_rows(client, db, act_as, fake_s3):
    ana = await _make_user(db, "ana")
    beto = await _make_user(db, "beto")
    await _make_full_dataset(db, ana)

    act_as(beto)
    response = await client.post("/exports/xlsx")

    assert response.status_code == 200
    key, _ = fake_s3.presigned[-1]
    assert key.startswith(f"exports/{beto.id}/"), "el export se escribe bajo el prefijo del usuario"


async def test_presigned_upload_url_is_namespaced_and_short_lived(client, db, act_as, fake_s3):
    """Lo que pide el issue sobre S3: el path lleva el user_id y la URL
    firmada no vive mas de 15 minutos."""
    ana = await _make_user(db, "ana")
    datos = await _make_full_dataset(db, ana)

    act_as(ana)
    response = await client.post(
        "/uploads/presign",
        json={
            "account_id": str(datos["account"].id),
            "filename": "extracto.pdf",
            "period_month": "2026-08-01",
            "requested_modules": ["flujo_mensual"],
        },
    )

    assert response.status_code == 200
    key, expires_in = fake_s3.presigned[-1]
    assert key.startswith(f"uploads/{ana.id}/")
    assert 0 < expires_in <= 900, "maximo 15 minutos"
