import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.assistant.service import call_claude, get_ai_settings
from app.modules.auth.models import User
from app.modules.content.media import media_asset_to_read
from app.modules.content.models import Content, ContentGenerationJob, ContentVariant
from app.modules.content.schemas import ContentVariantRead

GENERATION_SYSTEM_PROMPT = (
    "You are a social media copywriter for an internal marketing team. Write a single "
    "{platform} post based on the brief below. Return only the finished post text - "
    "no explanations, no markdown formatting, no quotation marks around it."
)


async def create_content(db: AsyncSession, workspace_id: uuid.UUID, title: str) -> Content:
    content = Content(workspace_id=workspace_id, title=title)
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


async def list_contents(
    db: AsyncSession, workspace_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Content], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(Content).where(Content.workspace_id == workspace_id)
        )
    ).scalar_one()

    result = await db.execute(
        select(Content)
        .where(Content.workspace_id == workspace_id)
        .order_by(Content.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_content(
    db: AsyncSession, workspace_id: uuid.UUID, content_id: uuid.UUID
) -> Content | None:
    result = await db.execute(
        select(Content).where(Content.id == content_id, Content.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def update_content_title(db: AsyncSession, content: Content, title: str) -> Content:
    content.title = title
    await db.commit()
    await db.refresh(content)
    return content


async def delete_content(db: AsyncSession, content: Content) -> None:
    await db.delete(content)
    await db.commit()


async def create_variant(
    db: AsyncSession,
    content_id: uuid.UUID,
    platform: str,
    text: str,
    media_type: str,
    payload_json: dict[str, Any],
) -> ContentVariant:
    variant = ContentVariant(
        content_id=content_id,
        platform=platform,
        text=text,
        media_type=media_type,
        payload_json=payload_json,
    )
    db.add(variant)
    await db.commit()
    return await get_variant(db, content_id, variant.id)  # type: ignore[return-value]


async def list_variants(db: AsyncSession, content_id: uuid.UUID) -> list[ContentVariant]:
    # populate_existing: guards against a stale in-memory media_links collection if a variant
    # object is already in this session's identity map from an earlier query in the request.
    result = await db.execute(
        select(ContentVariant)
        .options(selectinload(ContentVariant.media_links))
        .where(ContentVariant.content_id == content_id)
        .order_by(ContentVariant.platform)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def get_variant(
    db: AsyncSession, content_id: uuid.UUID, variant_id: uuid.UUID
) -> ContentVariant | None:
    result = await db.execute(
        select(ContentVariant)
        .options(selectinload(ContentVariant.media_links))
        .where(ContentVariant.id == variant_id, ContentVariant.content_id == content_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


def variant_to_read(variant: ContentVariant) -> ContentVariantRead:
    return ContentVariantRead(
        id=variant.id,
        content_id=variant.content_id,
        platform=variant.platform,
        text=variant.text,
        media_type=variant.media_type,
        payload_json=variant.payload_json,
        media=[media_asset_to_read(link.media_asset) for link in variant.media_links],
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


async def update_variant(
    db: AsyncSession,
    variant: ContentVariant,
    text: str | None,
    media_type: str | None,
    payload_json: dict[str, Any] | None,
) -> ContentVariant:
    if text is not None:
        variant.text = text
    if media_type is not None:
        variant.media_type = media_type
    if payload_json is not None:
        variant.payload_json = payload_json
    await db.commit()
    return await get_variant(db, variant.content_id, variant.id)  # type: ignore[return-value]


async def delete_variant(db: AsyncSession, variant: ContentVariant) -> None:
    await db.delete(variant)
    await db.commit()


async def create_generation_job(
    db: AsyncSession, content_id: uuid.UUID, platform: str, brief: str, requester: User
) -> ContentGenerationJob:
    job = ContentGenerationJob(
        content_id=content_id,
        platform=platform,
        brief=brief,
        status="pending",
        requested_by_email=requester.email,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_generation_job(
    db: AsyncSession, content_id: uuid.UUID, job_id: uuid.UUID
) -> ContentGenerationJob | None:
    result = await db.execute(
        select(ContentGenerationJob).where(
            ContentGenerationJob.id == job_id, ContentGenerationJob.content_id == content_id
        )
    )
    return result.scalar_one_or_none()


async def run_generation_job(db: AsyncSession, job_id: uuid.UUID) -> None:
    job = await db.get(ContentGenerationJob, job_id)
    if job is None or job.status != "pending":
        return

    job.status = "processing"
    await db.commit()

    content = await db.get(Content, job.content_id)
    if content is None:
        job.status = "failed"
        job.error_message = "The content draft no longer exists"
        await db.commit()
        return

    ai_settings = await get_ai_settings(db, content.workspace_id)
    if ai_settings is None:
        job.status = "failed"
        job.error_message = "The AI assistant is not configured for this workspace"
        await db.commit()
        return

    result = await call_claude(
        ai_settings,
        job.brief,
        system=GENERATION_SYSTEM_PROMPT.format(platform=job.platform),
    )

    if not result.succeeded:
        job.status = "failed"
        job.error_message = result.error_message
        await db.commit()
        return

    generated_text = result.text
    assert generated_text is not None  # guaranteed by call_claude when succeeded=True

    job.generated_text = generated_text
    job.status = "completed"
    job.completed_at = datetime.now(UTC)

    variant = (
        await db.execute(
            select(ContentVariant).where(
                ContentVariant.content_id == content.id, ContentVariant.platform == job.platform
            )
        )
    ).scalar_one_or_none()
    if variant is None:
        db.add(ContentVariant(content_id=content.id, platform=job.platform, text=generated_text))
    else:
        variant.text = generated_text

    await db.commit()
