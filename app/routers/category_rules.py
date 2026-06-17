import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.category_rule import CategoryRule
from app.models.user import User
from app.schemas.category_rule import CategoryRuleCreate, CategoryRuleRead

router = APIRouter(prefix="/category-rules", tags=["category-rules"])


@router.get("", response_model=list[CategoryRuleRead])
async def list_category_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(CategoryRule).where(CategoryRule.user_id == current_user.id)
    )
    return result.all()


@router.post("", response_model=CategoryRuleRead, status_code=201)
async def create_category_rule(
    body: CategoryRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(CategoryRule).where(
            CategoryRule.user_id == current_user.id, CategoryRule.keyword == body.keyword
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una regla para ese keyword")

    rule = CategoryRule(user_id=current_user.id, keyword=body.keyword, category=body.category, source="user")
    db.add(rule)
    await db.flush()
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_category_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.scalar(
        select(CategoryRule).where(CategoryRule.id == rule_id, CategoryRule.user_id == current_user.id)
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")

    await db.delete(rule)
