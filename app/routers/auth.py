from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.cognito import CognitoClient, get_cognito
from app.database import get_db
from app.middleware.auth import security
from app.schemas.auth import (
    ChallengeResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    TotpRequest,
)
from app.services.auth_service import get_or_create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
async def register(body: RegisterRequest, cognito: CognitoClient = Depends(get_cognito)):
    """Crea el usuario en Cognito. La confirmacion (email/2FA) se completa desde el cliente."""
    try:
        cognito_sub = cognito.sign_up(body.email, body.password, body.name)
    except cognito.client.exceptions.UsernameExistsException as exc:
        raise HTTPException(status_code=409, detail="El email ya esta registrado") from exc

    return RegisterResponse(user_id=cognito_sub, email=body.email)


@router.post("/login", response_model=TokenResponse | ChallengeResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    cognito: CognitoClient = Depends(get_cognito),
):
    try:
        result = cognito.initiate_auth(body.email, body.password)
    except cognito.client.exceptions.NotAuthorizedException as exc:
        raise HTTPException(status_code=401, detail="Credenciales invalidas") from exc

    if "ChallengeName" in result:
        return ChallengeResponse(challenge_name=result["ChallengeName"], session=result["Session"])

    return await _issue_tokens(db, result["AuthenticationResult"], body.email)


@router.post("/totp", response_model=TokenResponse)
async def submit_totp(
    body: TotpRequest,
    db: AsyncSession = Depends(get_db),
    cognito: CognitoClient = Depends(get_cognito),
):
    try:
        result = cognito.respond_to_mfa_challenge(body.session, body.email, body.code)
    except cognito.client.exceptions.CodeMismatchException as exc:
        raise HTTPException(status_code=401, detail="Codigo TOTP invalido") from exc

    return await _issue_tokens(db, result["AuthenticationResult"], body.email)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, cognito: CognitoClient = Depends(get_cognito)):
    try:
        result = cognito.refresh_tokens(body.refresh_token)
    except cognito.client.exceptions.NotAuthorizedException as exc:
        raise HTTPException(status_code=401, detail="Refresh token invalido o expirado") from exc

    auth_result = result["AuthenticationResult"]
    return TokenResponse(
        access_token=auth_result["AccessToken"],
        id_token=auth_result.get("IdToken"),
        refresh_token=body.refresh_token,
    )


@router.post("/logout")
async def logout(
    credentials=Depends(security),
    cognito: CognitoClient = Depends(get_cognito),
):
    cognito.global_sign_out(credentials.credentials)
    return {"detail": "Sesion cerrada"}


async def _issue_tokens(db: AsyncSession, auth_result: dict, email: str) -> TokenResponse:
    id_token = auth_result["IdToken"]
    claims = jwt.get_unverified_claims(id_token)
    await get_or_create_user(
        db,
        cognito_sub=claims["sub"],
        email=email,
        name=claims.get("name", ""),
    )

    return TokenResponse(
        access_token=auth_result["AccessToken"],
        refresh_token=auth_result.get("RefreshToken"),
        id_token=id_token,
    )
