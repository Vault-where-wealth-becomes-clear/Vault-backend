import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    """Deja un renglón en audit_log. actor_user_id=None significa que el
    cambio lo hizo un proceso automático, no una persona."""
    db.add(
        AuditLog(
            user_id=user_id,
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
        )
    )
    await db.flush()
