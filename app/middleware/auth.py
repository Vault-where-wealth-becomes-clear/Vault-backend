import time

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer()

# Cognito rota las claves de firma sin avisar. Un cache eterno hace que todo
# proceso ya levantado siga validando contra el set viejo hasta que lo
# reinicien, lo que se ve como una ola de 401 inexplicables para todos los
# usuarios a la vez.
_JWKS_TTL_SECONDS = 3600
# Piso entre refetch forzados: un `kid` desconocido dispara un refetch, y sin
# este piso cualquiera puede hacernos martillar a Cognito mandando tokens con
# kids al azar.
_JWKS_MIN_REFETCH_SECONDS = 60

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_forced_at: float = 0.0


async def _fetch_jwks() -> dict:
    url = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def _get_jwks(force_refresh: bool = False) -> dict:
    global _jwks_cache, _jwks_fetched_at, _jwks_forced_at

    now = time.monotonic()
    stale = _jwks_cache is None or now - _jwks_fetched_at >= _JWKS_TTL_SECONDS
    # El piso se mide contra el ultimo refetch *forzado*, no contra el ultimo
    # fetch a secas: si no, una rotacion detectada poco despues de un fetch
    # normal quedaria suprimida — que es justo el caso que esto cubre.
    forced = force_refresh and now - _jwks_forced_at >= _JWKS_MIN_REFETCH_SECONDS

    if stale or forced:
        _jwks_cache = await _fetch_jwks()
        _jwks_fetched_at = time.monotonic()
        if forced:
            _jwks_forced_at = _jwks_fetched_at
    return _jwks_cache


def _find_key(jwks: dict, kid: str) -> dict | None:
    return next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)


async def _decode_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = _find_key(await _get_jwks(), kid)
        if key is None:
            # Un kid que no está en el cache es justamente la señal de que
            # Cognito rotó: reintentar una vez con JWKS fresco antes de
            # rechazar el token.
            key = _find_key(await _get_jwks(force_refresh=True), kid)
        if key is None:
            raise HTTPException(status_code=401, detail="Token invalido")
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            options={"verify_aud": True},
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token expirado o invalido") from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = await _decode_token(credentials.credentials)
    cognito_sub = payload.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user = await db.scalar(select(User).where(User.cognito_sub == cognito_sub))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return user
