import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

MediaType = Literal["none", "image", "video", "carousel"]


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ContentUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ContentRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentListResponse(BaseModel):
    items: list[ContentRead]
    total: int
    limit: int
    offset: int


class ContentVariantCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    text: str = ""
    media_type: MediaType = "none"
    payload_json: dict[str, Any] = Field(default_factory=dict)


class ContentVariantUpdate(BaseModel):
    text: str | None = None
    media_type: MediaType | None = None
    payload_json: dict[str, Any] | None = None


class MediaAssetRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    mime_type: str
    size_bytes: int
    filename: str | None = None
    file_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaAssetListResponse(BaseModel):
    items: list[MediaAssetRead]
    total: int
    limit: int
    offset: int


class VariantMediaUpdate(BaseModel):
    """Replaces a variant's attached media, in display order."""

    media_asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class ContentVariantRead(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    platform: str
    text: str
    media_type: str
    payload_json: dict[str, Any]
    media: list[MediaAssetRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerationJobCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    brief: str = Field(min_length=1, max_length=4000)


class GenerationJobRead(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    platform: str
    brief: str
    status: str
    generated_text: str | None
    error_message: str | None
    requested_by_email: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
