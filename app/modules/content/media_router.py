import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership, get_current_user
from app.core.database import get_db
from app.core.storage import StorageError, resolve_path
from app.modules.audit.service import log_action
from app.modules.auth.models import User, WorkspaceMember
from app.modules.content import media
from app.modules.content.schemas import MediaAssetListResponse, MediaAssetRead

router = APIRouter(prefix="/media", tags=["media"])


@router.post("", response_model=MediaAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile,
    membership: WorkspaceMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        asset = await media.upload_media(db, membership.workspace_id, file)
    except media.MediaUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    await log_action(
        db,
        membership.workspace_id,
        current_user,
        "media.upload",
        target_type="media_asset",
        target_id=str(asset.id),
        details={"mime_type": asset.mime_type, "size_bytes": asset.size_bytes},
    )
    await db.commit()
    return media.media_asset_to_read(asset)


@router.get("", response_model=MediaAssetListResponse)
async def list_media(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    items, total = await media.list_media(db, membership.workspace_id, limit, offset)
    return MediaAssetListResponse(
        items=[media.media_asset_to_read(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await media.get_media(db, membership.workspace_id, media_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    try:
        await media.delete_media(db, asset)
    except media.MediaDeleteError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await log_action(
        db,
        membership.workspace_id,
        current_user,
        "media.delete",
        target_type="media_asset",
        target_id=str(media_id),
    )
    await db.commit()


@router.get("/{media_id}/file")
async def get_media_file(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Serves the raw bytes. Deliberately not auth-gated -- see `get_media_by_id`'s docstring:
    platforms like Meta fetch this URL server-to-server with no GoFlow session cookie."""
    asset = await media.get_media_by_id(db, media_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    try:
        path = resolve_path(asset.storage_key)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media not found"
        ) from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    return FileResponse(path, media_type=asset.mime_type)
