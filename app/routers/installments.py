import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.installment import Installment
from app.models.user import User
from app.schemas.installment import InstallmentRead, InstallmentUpdate

router = APIRouter(prefix="/installments", tags=["installments"])


@router.get("", response_model=list[InstallmentRead])
async def list_installments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Installment)
        .where(Installment.user_id == current_user.id)
        .order_by(Installment.next_due_date.asc())
    )
    return result.all()


@router.patch("/{installment_id}", response_model=InstallmentRead)
async def update_installment(
    installment_id: uuid.UUID,
    body: InstallmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    installment = await db.scalar(
        select(Installment).where(
            Installment.id == installment_id, Installment.user_id == current_user.id
        )
    )
    if not installment:
        raise HTTPException(status_code=404, detail="Cuota no encontrada")

    if body.amount_per_installment is not None:
        installment.amount_per_installment = body.amount_per_installment
    if body.total_installments is not None:
        installment.total_installments = body.total_installments

    await db.flush()
    return installment
