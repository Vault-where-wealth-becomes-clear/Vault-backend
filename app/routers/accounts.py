import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.plans import PLAN_FEATURES
from app.models.account import Account
from app.models.user import User
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Account).where(Account.user_id == current_user.id, Account.is_active.is_(True))
    )
    return result.all()


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(
    body: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    max_accounts = PLAN_FEATURES[current_user.plan.value]["max_accounts"]
    if max_accounts is not None:
        count = await db.scalar(
            select(func.count())
            .select_from(Account)
            .where(Account.user_id == current_user.id, Account.is_active.is_(True))
        )
        if count >= max_accounts:
            raise HTTPException(
                status_code=403,
                detail=f"El plan {current_user.plan.value} permite hasta {max_accounts} cuenta(s)",
            )

    account = Account(user_id=current_user.id, **body.model_dump())
    db.add(account)
    await db.flush()
    return account


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_owned_account(db, account_id, current_user.id)

    if body.name is not None:
        account.name = body.name
    if body.institution is not None:
        account.institution = body.institution

    await db.flush()
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_owned_account(db, account_id, current_user.id)
    account.is_active = False
    await db.flush()


async def _get_owned_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account:
    account = await db.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return account
