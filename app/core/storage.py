"""Local filesystem storage for uploaded media.

Single-instance internal tool (per Claude.md section 1), so a local disk directory shared
across containers via a volume is sufficient -- no object storage dependency to justify yet.
"""

import uuid
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

# Keep the allow-list narrow and explicit: only what the Facebook/mock connectors can actually
# use today (image) or are expected to need soon (video), per Claude.md's "text/image first"
# publishing guidance.
ALLOWED_MIME_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024


class StorageError(Exception):
    pass


def _storage_root() -> Path:
    return Path(settings.storage_root).resolve()


def save_file(workspace_id: uuid.UUID, mime_type: str, data: bytes) -> str:
    extension = ALLOWED_MIME_TYPES.get(mime_type)
    if extension is None:
        raise StorageError(f"Unsupported media type: {mime_type}")
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise StorageError(f"File exceeds the {MAX_UPLOAD_SIZE_BYTES} byte upload limit")

    storage_key = f"{workspace_id}/{uuid.uuid4().hex}{extension}"
    path = _storage_root() / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return storage_key


def resolve_path(storage_key: str) -> Path:
    """Resolves a DB-stored (never client-supplied) storage_key to an on-disk path."""
    root = _storage_root()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise StorageError("Resolved path escapes the storage root")
    return path


def delete_file(storage_key: str) -> None:
    resolve_path(storage_key).unlink(missing_ok=True)
