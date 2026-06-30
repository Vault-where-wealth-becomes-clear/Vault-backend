import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.account import Account
from app.models.category_rule import CategoryRule
from app.models.enums import CurrencyType, RuleSource, UploadStatus
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/manual", response_model=TransactionRead, status_code=201)
async def create_manual_transaction(
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await db.scalar(
        select(Account).where(Account.id == body.account_id, Account.user_id == current_user.id)
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    sign = Decimal("1") if body.transaction_type == "ingreso" else Decimal("-1")
    signed = Decimal(str(abs(body.amount))) * sign

    if body.currency == CurrencyType.USD:
        amount_ars = Decimal("0")
        amount_usd = signed
    else:
        amount_ars = signed
        amount_usd = None

    transaction = Transaction(
        user_id=current_user.id,
        account_id=body.account_id,
        upload_id=None,
        date=body.date,
        description=body.description or "Movimiento manual",
        amount_ars=amount_ars,
        amount_usd=amount_usd,
        currency=body.currency,
        category=body.category,
        confidence=Decimal("1.0"),
        needs_review=False,
        is_corrected=True,
    )
    db.add(transaction)

    # Actualiza el saldo de la cuenta
    account.current_balance = (account.current_balance or Decimal("0")) + signed

    await db.flush()
    return transaction


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    account_id: uuid.UUID | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    if category:
        query = query.where(Transaction.category == category)
    if date_from:
        query = query.where(Transaction.date >= date_from)
    if date_to:
        query = query.where(Transaction.date <= date_to)

    result = await db.scalars(query.order_by(Transaction.date.desc()))
    return result.all()


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def correct_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transaction = await db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == current_user.id
        )
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")

    transaction.category = body.category
    transaction.is_corrected = True
    transaction.needs_review = False

    if body.remember_rule:
        keyword = transaction.description.split(" ")[0]
        rule = await db.scalar(
            select(CategoryRule).where(
                CategoryRule.user_id == current_user.id, CategoryRule.keyword == keyword
            )
        )
        if rule:
            rule.category = body.category
        else:
            db.add(
                CategoryRule(
                    user_id=current_user.id,
                    keyword=keyword,
                    category=body.category,
                    source=RuleSource.user,
                )
            )

    await db.flush()
    return transaction


@router.get("/review/{upload_id}", response_model=list[TransactionRead])
async def get_review_queue(
    upload_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Transaction).where(
            Transaction.upload_id == upload_id,
            Transaction.user_id == current_user.id,
            Transaction.needs_review.is_(True),
        )
    )
    return result.all()


@router.post("/confirm-review/{upload_id}")
async def confirm_review(
    upload_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    upload = await db.scalar(
        select(Upload).where(Upload.id == upload_id, Upload.user_id == current_user.id)
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload no encontrado")

    pending = await db.scalar(
        select(Transaction).where(
            Transaction.upload_id == upload_id, Transaction.needs_review.is_(True)
        )
    )
    if pending:
        raise HTTPException(status_code=400, detail="Quedan transacciones sin revisar")

    upload.status = UploadStatus.done
    await db.flush()
    return {"detail": "Upload confirmado"}
