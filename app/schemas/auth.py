from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr


class ConfirmRequest(BaseModel):
    email: EmailStr
    code: str


class ResendCodeRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TotpRequest(BaseModel):
    email: EmailStr
    session: str
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    id_token: str | None = None
    token_type: str = "Bearer"


class ChallengeResponse(BaseModel):
    challenge_name: str
    session: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
