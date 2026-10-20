import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership, get_current_user
from app.core.database import get_db
from app.modules.assistant import service
from app.modules.assistant.schemas import (
    UserRequestCreate,
    UserRequestListResponse,
    UserRequestRead,
)
from app.modules.audit.service import log_action
from app.modules.auth.models import User, WorkspaceMember

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=UserRequestRead, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: UserRequestCreate,
    membership: WorkspaceMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ai_settings = await service.get_ai_settings(db, membership.workspace_id)
    if ai_settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI assistant is not configured for this workspace yet (see Settings).",
        )

    request = await service.create_request(
        db, membership.workspace_id, current_user, payload.prompt
    )
    await service.answer_request(db, request, ai_settings)

    await log_action(
        db,
        membership.workspace_id,
        current_user,
        "requests.create",
        target_type="user_request",
        target_id=str(request.id),
        details={"status": request.status},
    )
    await db.commit()
    await db.refresh(request)
    return request


@router.get("", response_model=UserRequestListResponse)
async def list_requests(
    q: str | None = Query(default=None, description="Free-text search"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_requests(db, membership.workspace_id, limit, offset, search=q)
    return UserRequestListResponse(
        items=[UserRequestRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=UserRequestRead)
async def get_request(
    request_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    request = await service.get_request(db, membership.workspace_id, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request
