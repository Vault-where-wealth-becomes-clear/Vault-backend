"""El job diario de sincronización de TC MEP no debe pisar lo que un usuario
ya cargó a mano, y tiene que rechazar llamadas sin el secreto interno."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.models.enums import MepSource
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.routers import internal as internal_router
from app.services.mep_ingestion import MepQuote

_HOY = date.today().replace(day=1)


def _fake_quote() -> MepQuote:
    return MepQuote(buy_rate=1180.0, sell_rate=1200.0, fetched_at=datetime.now(), source="dolarapi")


def _fake_async(value):
    async def _inner():
        return value

    return _inner


async def _make_user(db) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()
    return user.id


async def test_sync_rejects_requests_without_the_internal_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_sync_secret", "el-secreto")
    resp = await client.post("/internal/exchange-rates/sync-mep")
    assert resp.status_code == 401


async def test_sync_rejects_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_sync_secret", "")
    resp = await client.post(
        "/internal/exchange-rates/sync-mep", headers={"x-internal-secret": "cualquier-cosa"}
    )
    assert resp.status_code == 401


async def test_sync_creates_a_rate_for_a_user_with_none(client, db, monkeypatch):
    monkeypatch.setattr(settings, "internal_sync_secret", "el-secreto")
    monkeypatch.setattr(internal_router, "fetch_mep_quote", _fake_async(_fake_quote()))

    user_id = await _make_user(db)
    await db.flush()

    resp = await client.post(
        "/internal/exchange-rates/sync-mep", headers={"x-internal-secret": "el-secreto"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["users_created"] == 1
    assert body["sell_rate"] == 1200.0
    assert body["buy_rate"] == 1180.0

    rate = await db.scalar(select(ExchangeRate).where(ExchangeRate.user_id == user_id))
    assert rate.mep_rate == Decimal("1200")
    assert rate.buy_rate == Decimal("1180")
    assert rate.source == MepSource.api


async def test_sync_never_overwrites_a_manually_declared_rate(client, db, monkeypatch):
    monkeypatch.setattr(settings, "internal_sync_secret", "el-secreto")
    monkeypatch.setattr(internal_router, "fetch_mep_quote", _fake_async(_fake_quote()))

    user_id = await _make_user(db)
    db.add(
        ExchangeRate(
            user_id=user_id,
            period_month=_HOY,
            mep_rate=Decimal("999"),
            source=MepSource.manual,
        )
    )
    await db.flush()

    resp = await client.post(
        "/internal/exchange-rates/sync-mep", headers={"x-internal-secret": "el-secreto"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["users_skipped_manual"] == 1
    assert body["users_created"] == 0
    assert body["users_updated"] == 0

    rate = await db.scalar(select(ExchangeRate).where(ExchangeRate.user_id == user_id))
    assert rate.mep_rate == Decimal(
        "999"
    ), "un TC cargado a mano no puede ser pisado por la sincronizacion automatica"
