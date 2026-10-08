import time

import pytest
from fastapi import HTTPException
from jose import jwt

from app.middleware import auth


def _jwks(*kids: str) -> dict:
    return {"keys": [{"kid": kid} for kid in kids]}


def _token_with_kid(kid: str) -> str:
    return jwt.encode({"sub": "abc"}, "secret", algorithm="HS256", headers={"kid": kid})


def _reset_cache() -> None:
    auth._jwks_cache = None
    auth._jwks_fetched_at = 0.0
    auth._jwks_forced_at = 0.0


async def test_jwks_is_cached_within_ttl_and_refetched_after_it(monkeypatch):
    _reset_cache()
    calls: list[int] = []

    async def fake_fetch() -> dict:
        calls.append(1)
        return _jwks("k1")

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)

    await auth._get_jwks()
    await auth._get_jwks()
    assert len(calls) == 1, "dentro del TTL tiene que servir del cache"

    auth._jwks_fetched_at = time.monotonic() - auth._JWKS_TTL_SECONDS - 1
    await auth._get_jwks()
    assert len(calls) == 2, "pasado el TTL tiene que volver a pedir el JWKS"

    _reset_cache()


async def test_unknown_kid_triggers_refetch_so_a_rotated_key_still_validates(monkeypatch):
    """El bug original: tras una rotacion de claves en Cognito, el proceso
    seguia validando contra el JWKS viejo y devolvia 401 para siempre."""
    _reset_cache()
    calls: list[int] = []

    async def fake_fetch() -> dict:
        calls.append(1)
        # Primera llamada: JWKS viejo. Segunda: el set ya rotado.
        return _jwks("k1") if len(calls) == 1 else _jwks("k1", "k2")

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)

    with pytest.raises(HTTPException) as excinfo:
        await auth._decode_token(_token_with_kid("k2"))

    # La clave rotada se encontro: el fallo llega despues, en jwt.decode (la
    # clave del test no es una RS256 real), no en el lookup del kid.
    assert excinfo.value.detail == "Token expirado o invalido"
    assert len(calls) == 2, "un kid desconocido tiene que forzar un refetch"

    _reset_cache()


async def test_repeated_unknown_kids_do_not_hammer_cognito(monkeypatch):
    """Sin piso entre refetch, mandar tokens con kids al azar seria una via
    directa para que cualquiera nos haga martillar el endpoint de Cognito."""
    _reset_cache()
    calls: list[int] = []

    async def fake_fetch() -> dict:
        calls.append(1)
        return _jwks("k1")

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)

    for _ in range(5):
        try:
            await auth._decode_token(_token_with_kid("desconocido"))
        except HTTPException:
            pass

    assert len(calls) == 2, (
        "un refetch forzado por ventana: el primero llena el cache, el segundo "
        "es el que cubre la rotacion, y los siguientes caen bajo el piso"
    )

    _reset_cache()
