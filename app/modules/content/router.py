import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership, get_current_user
from app.core.database import get_db
from app.modules.audit.service import log_action
from app.modules.auth.models import User, WorkspaceMember
from app.modules.content import service
from app.modules.content.models import Content, ContentGenerationJob, ContentVariant
from app.modules.content.schemas import (
    ContentCreate,
    ContentListResponse,
    ContentRead,
    ContentUpdate,
    ContentVariantCreate,
    ContentVariantRead,
    ContentVariantUpdate,
    GenerationJobCreate,
    GenerationJobRead,
)
from app.modules.publishing import service as publishing_service
from app.modules.publishing.schemas import PublishingJobRead, ScheduleRequest
from app.tasks.jobs import generate_content_job
from app.tasks.queue import generation_queue

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await service.create_content(db, membership.workspace_id, payload.title)
    await log_action(
        db,
        membership.workspace_id,
        current_user,
        "content.create",
        target_type="content",
        target_id=str(content.id),
        details={"title": content.title},
    )
    await db.commit()
    return content


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await service.update_content_title(db, content, payload.title)
    await log_action(
        db,
        content.workspace_id,
        current_user,
        "content.update",
        target_type="content",
        target_id=str(content.id),
        details={"title": payload.title},
    )
    await db.commit()
    return updated


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content: Content = Depends(_get_owned_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if content.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft content can be deleted",
        )
    content_id = str(content.id)
    workspace_id = content.workspace_id
    title = content.title
    await service.delete_content(db, content)
    await log_action(
        db,
        workspace_id,
        current_user,
        "content.delete",
        target_type="content",
        target_id=content_id,
        details={"title": title},
    )
    await db.commit()


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if content.status not in ("draft", "failed", "partial_failure"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Content in status '{content.status}' cannot be (re)scheduled",
        )
    try:
        jobs = await publishing_service.schedule_content(db, content, payload.assignments)
    except publishing_service.ScheduleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    await log_action(
        db,
        content.workspace_id,
        current_user,
        "content.schedule",
        target_type="content",
        target_id=str(content.id),
        details={"job_count": len(jobs), "platforms": [a.platform for a in payload.assignments]},
    )
    await db.commit()
    return jobs


@router.post("/{content_id}/cancel")
async def cancel_content(
    content: Content = Depends(_get_owned_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cancelled = await publishing_service.cancel_content_jobs(db, content)
    await log_action(
        db,
        content.workspace_id,
        current_user,
        "content.cancel",
        target_type="content",
        target_id=str(content.id),
        details={"cancelled_jobs": cancelled},
    )
    await db.commit()
    return {"cancelled_jobs": cancelled}


@router.post(
    "/{content_id}/generate", response_model=GenerationJobRead, status_code=status.HTTP_201_CREATED
)
async def generate_variant(
    payload: GenerationJobCreate,
    content: Content = Depends(_get_owned_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if content.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Content must be a draft to generate or regenerate a variant",
        )
    job = await service.create_generation_job(
        db, content.id, payload.platform, payload.brief, current_user
    )
    generation_queue.enqueue(generate_content_job, str(job.id))

    await log_action(
        db,
        content.workspace_id,
        current_user,
        "content.generate_requested",
        target_type="content_generation_job",
        target_id=str(job.id),
        details={"platform": payload.platform},
    )
    await db.commit()
    return job


@router.get("/{content_id}/generation-jobs/{job_id}", response_model=GenerationJobRead)
async def get_generation_job(
    job_id: uuid.UUID,
    content: Content = Depends(_get_owned_content),
    db: AsyncSession = Depends(get_db),
) -> ContentGenerationJob:
    job = await service.get_generation_job(db, content.id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found"
        )
    return job
