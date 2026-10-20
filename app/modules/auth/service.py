import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import verify_password
from app.modules.auth.models import User, WorkspaceMember


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return result.scalar_one_or_none()


async def get_primary_membership(db: AsyncSession, user_id: uuid.UUID) -> WorkspaceMember | None:
    result = await db.execute(
        select(WorkspaceMember)
        .options(joinedload(WorkspaceMember.workspace))
        .where(WorkspaceMember.user_id == user_id)
        .order_by(WorkspaceMember.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()
