import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.core.database import get_db
from app.modules.auth.models import WorkspaceMember
from app.modules.content import service
from app.modules.content.models import Content, ContentVariant
from app.modules.content.schemas import (
    ContentCreate,
    ContentListResponse,
    ContentRead,
    ContentUpdate,
    ContentVariantCreate,
    ContentVariantRead,
    ContentVariantUpdate,
)
from app.modules.publishing import service as publishing_service
from app.modules.publishing.schemas import PublishingJobRead, ScheduleRequest

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


async def _get_owned_variant(
    variant_id: uuid.UUID,
    content: Content = Depends(_get_owned_content),
    db: AsyncSession = Depends(get_db),
) -> ContentVariant:
    variant = await service.get_variant(db, content.id, variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    return variant


@router.post(
    "/{content_id}/variants",
    response_model=ContentVariantRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_variant(
    payload: ContentVariantCreate,
    content: Content = Depends(_get_owned_content),
    db: AsyncSession = Depends(get_db),
):
    existing = await service.list_variants(db, content.id)
    if any(v.platform == payload.platform for v in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A variant for platform '{payload.platform}' already exists",
        )
    return await service.create_variant(
        db, content.id, payload.platform, payload.text, payload.media_type, payload.payload_json
    )


@router.get("/{content_id}/variants", response_model=list[ContentVariantRead])
async def list_variants(
    content: Content = Depends(_get_owned_content), db: AsyncSession = Depends(get_db)
):
    return await service.list_variants(db, content.id)


@router.patch("/{content_id}/variants/{variant_id}", response_model=ContentVariantRead)
async def update_variant(
    payload: ContentVariantUpdate,
    variant: ContentVariant = Depends(_get_owned_variant),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_variant(
        db, variant, payload.text, payload.media_type, payload.payload_json
    )


@router.delete("/{content_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variant(
    variant: ContentVariant = Depends(_get_owned_variant), db: AsyncSession = Depends(get_db)
):
    await service.delete_variant(db, variant)


@router.post("/{content_id}/schedule", response_model=list[PublishingJobRead])
async def schedule_content(
    payload: ScheduleRequest,
    content: Content = Depends(_get_owned_content),
    db: AsyncSession = Depends(get_db),
):
    if content.status not in ("draft", "failed", "partial_failure"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Content in status '{content.status}' cannot be (re)scheduled",
        )
    try:
        return await publishing_service.schedule_content(db, content, payload.assignments)
    except publishing_service.ScheduleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.post("/{content_id}/cancel")
async def cancel_content(
    content: Content = Depends(_get_owned_content), db: AsyncSession = Depends(get_db)
):
    cancelled = await publishing_service.cancel_content_jobs(db, content)
    return {"cancelled_jobs": cancelled}
