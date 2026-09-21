"""forgot-password no puede filtrar si un email esta registrado: la
respuesta tiene que ser identica exista o no la cuenta."""

from app.aws.cognito import get_cognito
from app.main import app


class _Exceptions:
    """Nombres calcados de botocore (cognito-idp) — no llevan sufijo Error."""

    class UserNotFoundException(Exception):  # noqa: N818
        pass

    class InvalidParameterException(Exception):  # noqa: N818
        pass

    class LimitExceededException(Exception):  # noqa: N818
        pass

    class CodeMismatchException(Exception):  # noqa: N818
        pass

    class ExpiredCodeException(Exception):  # noqa: N818
        pass

    class InvalidPasswordException(Exception):  # noqa: N818
        pass


class _FakeBotoClient:
    exceptions = _Exceptions


class _FakeCognito:
    def __init__(self, raise_on_forgot=None, raise_on_confirm=None):
        self.client = _FakeBotoClient()
        self.forgot_password_calls: list[str] = []
        self.confirm_calls: list[tuple[str, str, str]] = []
        self._raise_on_forgot = raise_on_forgot
        self._raise_on_confirm = raise_on_confirm

    def forgot_password(self, email: str) -> None:
        self.forgot_password_calls.append(email)
        if self._raise_on_forgot:
            raise self._raise_on_forgot

    def confirm_forgot_password(self, email: str, code: str, new_password: str) -> None:
        self.confirm_calls.append((email, code, new_password))
        if self._raise_on_confirm:
            raise self._raise_on_confirm


async def test_forgot_password_gives_the_same_response_for_an_unknown_email(client):
    fake = _FakeCognito(raise_on_forgot=_Exceptions.UserNotFoundException())
    app.dependency_overrides[get_cognito] = lambda: fake
    try:
        resp = await client.post("/auth/forgot-password", json={"email": "no-existe@test.com"})
    finally:
        app.dependency_overrides.pop(get_cognito, None)

    assert resp.status_code == 200
    assert "registrado" in resp.json()["detail"]


async def test_forgot_password_triggers_cognito_for_a_known_email(client):
    fake = _FakeCognito()
    app.dependency_overrides[get_cognito] = lambda: fake
    try:
        resp = await client.post("/auth/forgot-password", json={"email": "ana@test.com"})
    finally:
        app.dependency_overrides.pop(get_cognito, None)

    assert resp.status_code == 200
    assert fake.forgot_password_calls == ["ana@test.com"]


async def test_confirm_forgot_password_resets_via_cognito(client):
    fake = _FakeCognito()
    app.dependency_overrides[get_cognito] = lambda: fake
    try:
        resp = await client.post(
            "/auth/confirm-forgot-password",
            json={"email": "ana@test.com", "code": "123456", "new_password": "NuevaClave123!"},
        )
    finally:
        app.dependency_overrides.pop(get_cognito, None)

    assert resp.status_code == 200
    assert fake.confirm_calls == [("ana@test.com", "123456", "NuevaClave123!")]


async def test_confirm_forgot_password_treats_unknown_email_the_same_as_bad_code(client):
    fake = _FakeCognito(raise_on_confirm=_Exceptions.UserNotFoundException())
    app.dependency_overrides[get_cognito] = lambda: fake
    try:
        resp = await client.post(
            "/auth/confirm-forgot-password",
            json={"email": "no-existe@test.com", "code": "123456", "new_password": "x"},
        )
    finally:
        app.dependency_overrides.pop(get_cognito, None)

    assert resp.status_code == 400
    assert resp.json()["error"] == "Código inválido"
