import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.core.database import get_db
from app.modules.auth.models import WorkspaceMember
from app.modules.content import service
from app.modules.content.models import Content
from app.modules.content.schemas import (
    ContentCreate,
    ContentListResponse,
    ContentRead,
    ContentUpdate,
)

router = APIRouter(prefix="/contents", tags=["content"])


async def _get_owned_content(
    content_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> Content:
    content = await service.get_content(db, membership.workspace_id, content_id)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content


@router.post("", response_model=ContentRead, status_code=status.HTTP_201_CREATED)
async def create_content(
    payload: ContentCreate,
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_content(db, membership.workspace_id, payload.title)


@router.get("", response_model=ContentListResponse)
async def list_contents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_contents(db, membership.workspace_id, limit, offset)
    return ContentListResponse(
        items=[ContentRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{content_id}", response_model=ContentRead)
async def get_content(content: Content = Depends(_get_owned_content)):
    return content


@router.patch("/{content_id}", response_model=ContentRead)
async def update_content(
    payload: ContentUpdate,
    content: Content = Depends(_get_owned_content),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_content_title(db, content, payload.title)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content: Content = Depends(_get_owned_content), db: AsyncSession = Depends(get_db)
):
    if content.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft content can be deleted",
        )
    await service.delete_content(db, content)
