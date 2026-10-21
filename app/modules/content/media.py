import uuid

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.storage import (
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
    StorageError,
)
from app.core.storage import delete_file as delete_stored_file
from app.core.storage import save_file as save_stored_file
from app.modules.content.models import ContentVariant, ContentVariantMedia, MediaAsset
from app.modules.content.schemas import MediaAssetRead

settings = get_settings()

MAX_VARIANT_MEDIA = 10


class MediaUploadError(Exception):
    pass


class MediaDeleteError(Exception):
    pass


class VariantMediaError(Exception):
    pass


def media_asset_to_read(asset: MediaAsset) -> MediaAssetRead:
    return MediaAssetRead(
        id=asset.id,
        workspace_id=asset.workspace_id,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        filename=(asset.asset_metadata or {}).get("filename"),
        file_url=f"{settings.app_base_url}/api/v1/media/{asset.id}/file",
        created_at=asset.created_at,
    )


async def upload_media(db: AsyncSession, workspace_id: uuid.UUID, file: UploadFile) -> MediaAsset:
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise MediaUploadError(f"Unsupported file type: {mime_type or 'unknown'}")

    data = await file.read()
    if not data:
        raise MediaUploadError("Uploaded file is empty")
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise MediaUploadError(f"File exceeds the {MAX_UPLOAD_SIZE_BYTES} byte upload limit")

    try:
        storage_key = save_stored_file(workspace_id, mime_type, data)
    except StorageError as exc:
        raise MediaUploadError(str(exc)) from exc

    asset = MediaAsset(
        workspace_id=workspace_id,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=len(data),
        asset_metadata={"filename": file.filename} if file.filename else {},
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def list_media(
    db: AsyncSession, workspace_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[MediaAsset], int]:
    total = (
        await db.execute(
            select(func.count())
            .select_from(MediaAsset)
            .where(MediaAsset.workspace_id == workspace_id)
        )
    ).scalar_one()

    result = await db.execute(
        select(MediaAsset)
        .where(MediaAsset.workspace_id == workspace_id)
        .order_by(MediaAsset.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_media(
    db: AsyncSession, workspace_id: uuid.UUID, media_id: uuid.UUID
) -> MediaAsset | None:
    result = await db.execute(
        select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def get_media_by_id(db: AsyncSession, media_id: uuid.UUID) -> MediaAsset | None:
    """No workspace check -- only for the public, unauthenticated file-serving endpoint.

    The platform (e.g. Meta's servers) fetches media by URL with no session cookie, so the
    `/media/{id}/file` route can't require auth. The UUID id is unguessable, which is the same
    tradeoff most apps make for provider-fetched media URLs.
    """
    return await db.get(MediaAsset, media_id)


async def delete_media(db: AsyncSession, asset: MediaAsset) -> None:
    in_use = (
        await db.execute(
            select(func.count())
            .select_from(ContentVariantMedia)
            .where(ContentVariantMedia.media_asset_id == asset.id)
        )
    ).scalar_one()
    if in_use:
        raise MediaDeleteError("Media is attached to a content variant; remove it there first")

    storage_key = asset.storage_key
    await db.delete(asset)
    await db.commit()
    delete_stored_file(storage_key)


def derive_media_type(assets: list[MediaAsset]) -> str:
    """Infers the variant's media_type from what's actually attached.

    Mixed carousels aren't a real platform concept here -- more than one asset always means
    "carousel"; a single video is "video"; a single image is "image".
    """
    if not assets:
        return "none"
    if len(assets) > 1:
        return "carousel"
    return "video" if assets[0].mime_type.startswith("video/") else "image"


async def get_variant_media_urls(db: AsyncSession, variant_id: uuid.UUID) -> list[str]:
    variant = await _variant_with_media(db, variant_id)
    return [media_asset_to_read(link.media_asset).file_url for link in variant.media_links]


async def _variant_with_media(db: AsyncSession, variant_id: uuid.UUID) -> ContentVariant:
    # populate_existing: `variant` is already in the session's identity map (loaded earlier in
    # this request by get_variant, with media_links possibly empty) -- without this, selectinload
    # would skip re-fetching a relationship that's already "loaded", returning stale data.
    result = await db.execute(
        select(ContentVariant)
        .options(selectinload(ContentVariant.media_links))
        .where(ContentVariant.id == variant_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def set_variant_media(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    variant: ContentVariant,
    media_asset_ids: list[uuid.UUID],
) -> ContentVariant:
    if len(media_asset_ids) > MAX_VARIANT_MEDIA:
        raise VariantMediaError(f"A variant can have at most {MAX_VARIANT_MEDIA} media items")

    assets: list[MediaAsset] = []
    for media_id in media_asset_ids:
        asset = await get_media(db, workspace_id, media_id)
        if asset is None:
            raise VariantMediaError(f"Media asset {media_id} not found in this workspace")
        assets.append(asset)

    await db.execute(
        delete(ContentVariantMedia).where(ContentVariantMedia.content_variant_id == variant.id)
    )
    for position, asset in enumerate(assets):
        db.add(
            ContentVariantMedia(
                content_variant_id=variant.id, media_asset_id=asset.id, position=position
            )
        )
    variant.media_type = derive_media_type(assets)
    await db.commit()
    return await _variant_with_media(db, variant.id)
