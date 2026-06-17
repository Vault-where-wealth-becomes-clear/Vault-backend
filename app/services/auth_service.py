from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_or_create_user(db: AsyncSession, cognito_sub: str, email: str, name: str) -> User:
    """Upsert del usuario local en base al sub de Cognito. Se llama tras login/registro."""
    user = await db.scalar(select(User).where(User.cognito_sub == cognito_sub))
    if user:
        return user

    user = User(cognito_sub=cognito_sub, email=email, name=name)
    db.add(user)
    await db.flush()
    return user
