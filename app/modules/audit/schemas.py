import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogRead(BaseModel):
    id: uuid.UUID
    actor_email: str
    action: str
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int


class ReleaseCreate(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ReleaseRead(BaseModel):
    id: uuid.UUID
    version: str
    title: str
    description: str | None
    created_by_email: str
    released_at: datetime

    model_config = {"from_attributes": True}
