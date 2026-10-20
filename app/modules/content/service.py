import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import Content


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
