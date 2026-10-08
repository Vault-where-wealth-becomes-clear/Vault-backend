"""Los endpoints de credenciales son el blanco clasico de fuerza bruta y
credential stuffing. Antes solo `POST /uploads/presign` tenia limite."""

import pytest

from app.aws.cognito import get_cognito
from app.limiter import limiter
from app.main import app


class _FakeCognito:
    """Devuelve siempre el challenge de MFA: el login responde 200 sin tocar
    Cognito ni la base, asi el test mide el limite y nada mas."""

    def initiate_auth(self, email: str, password: str) -> dict:
        return {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "sesion-de-prueba"}

    def sign_up(self, email: str, password: str, name: str) -> str:
        return "sub-de-prueba"


@pytest.fixture(autouse=True)
def fake_cognito_and_clean_limiter():
    limiter.reset()
    app.dependency_overrides[get_cognito] = _FakeCognito
    yield
    app.dependency_overrides.pop(get_cognito, None)
    limiter.reset()


async def test_login_is_rate_limited(client):
    payload = {"email": "atacante@test.com", "password": "loQueSea"}

    statuses = [(await client.post("/auth/login", json=payload)).status_code for _ in range(31)]

    assert statuses[:30] == [200] * 30, "los primeros 30 intentos tienen que pasar"
    assert statuses[30] == 429, "el intento 31 en el mismo minuto tiene que cortarse"


async def test_register_is_rate_limited(client):
    """Mas estricto que el login: crear cuentas en masa no tiene caso legitimo."""
    payload = {"email": "spam@test.com", "password": "Password1!", "name": "Spam"}

    statuses = [(await client.post("/auth/register", json=payload)).status_code for _ in range(21)]

    assert statuses[20] == 429
