from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.cognito import CognitoClient, get_cognito
from app.aws.s3 import S3Client, get_s3
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.account import Account
from app.models.financial_snapshot import FinancialSnapshot
from app.models.upload import Upload
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        current_user.name = body.name
    if body.base_currency is not None:
        current_user.base_currency = body.base_currency

    await db.flush()
    return current_user


@router.delete("/me/data", status_code=204)
async def delete_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3: S3Client = Depends(get_s3),
):
    """Borra uploads, transacciones, snapshots y resetea balances. El usuario queda intacto."""
    await s3.delete_prefix(f"uploads/{current_user.id}/")

    await db.execute(delete(FinancialSnapshot).where(FinancialSnapshot.user_id == current_user.id))
    await db.execute(delete(Upload).where(Upload.user_id == current_user.id))
    await db.execute(
        update(Account)
        .where(Account.user_id == current_user.id)
        .values(current_balance=Decimal("0"))
    )


@router.delete("/me", status_code=204)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3: S3Client = Depends(get_s3),
    cognito: CognitoClient = Depends(get_cognito),
):
    """Borra al usuario por completo: archivos en S3, identidad en Cognito y todas sus filas en DB.

    El borrado de DB depende de los ON DELETE CASCADE definidos en las foreign keys
    hacia users.id (directas o via uploads/transactions) — no hace falta borrar
    cuentas, uploads, transacciones, cuotas ni reglas a mano.
    """
    await s3.delete_prefix(f"uploads/{current_user.id}/")
    await s3.delete_prefix(f"exports/{current_user.id}/")
    cognito.admin_delete_user(current_user.email)
    await db.delete(current_user)
