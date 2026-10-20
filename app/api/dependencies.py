import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import SESSION_COOKIE_NAME, read_session_token
from app.modules.auth.models import User, WorkspaceMember
from app.modules.auth.service import get_primary_membership, get_user_by_id


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user_id_raw = read_session_token(token) if token else None
    if user_id_raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = await get_user_by_id(db, uuid.UUID(user_id_raw))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_current_membership(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> WorkspaceMember:
    membership = await get_primary_membership(db, current_user.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No workspace membership")
    return membership


def require_role(*roles: str) -> Callable:
    async def _check(
        membership: WorkspaceMember = Depends(get_current_membership),
    ) -> WorkspaceMember:
        if membership.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return membership

    return _check
