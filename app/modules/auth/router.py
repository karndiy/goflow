from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
)
from app.modules.audit.service import log_action
from app.modules.auth.models import User, WorkspaceMember
from app.modules.auth.schemas import LoginRequest, UserRead, WorkspaceRead, WorkspaceUpdate
from app.modules.auth.service import authenticate_user, get_primary_membership

settings = get_settings()

router = APIRouter(tags=["auth"])

require_workspace_admin = Depends(require_role("owner", "admin"))


@router.post("/auth/login", response_model=UserRead)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    user = await authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    token = create_session_token(str(user.id))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )

    membership = await get_primary_membership(db, user.id)
    if membership is not None:
        await log_action(db, membership.workspace_id, user, "auth.login")
        await db.commit()

    return user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


@router.get("/auth/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/workspace", response_model=WorkspaceRead)
async def get_workspace(
    membership: WorkspaceMember = Depends(get_current_membership),
):
    return membership.workspace


@router.patch("/workspace", response_model=WorkspaceRead)
async def update_workspace(
    payload: WorkspaceUpdate,
    membership: WorkspaceMember = require_workspace_admin,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = membership.workspace
    changes = {}
    if payload.name is not None:
        changes["name"] = payload.name
        workspace.name = payload.name
    if payload.timezone is not None:
        changes["timezone"] = payload.timezone
        workspace.timezone = payload.timezone
    if changes:
        await log_action(
            db,
            membership.workspace_id,
            current_user,
            "workspace.update",
            target_type="workspace",
            target_id=str(workspace.id),
            details=changes,
        )
    await db.commit()
    await db.refresh(workspace)
    return workspace
