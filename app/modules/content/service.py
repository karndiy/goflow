import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import Content, ContentVariant


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
    await db.refresh(variant)
    return variant


async def list_variants(db: AsyncSession, content_id: uuid.UUID) -> list[ContentVariant]:
    result = await db.execute(
        select(ContentVariant)
        .where(ContentVariant.content_id == content_id)
        .order_by(ContentVariant.platform)
    )
    return list(result.scalars().all())


async def get_variant(
    db: AsyncSession, content_id: uuid.UUID, variant_id: uuid.UUID
) -> ContentVariant | None:
    result = await db.execute(
        select(ContentVariant).where(
            ContentVariant.id == variant_id, ContentVariant.content_id == content_id
        )
    )
    return result.scalar_one_or_none()


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
    await db.refresh(variant)
    return variant


async def delete_variant(db: AsyncSession, variant: ContentVariant) -> None:
    await db.delete(variant)
    await db.commit()
