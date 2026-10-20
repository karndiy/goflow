import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.assistant.models import DEFAULT_CLAUDE_MODEL


class AISettingsRead(BaseModel):
    model: str
    has_api_key: bool
    updated_at: datetime


class AISettingsWrite(BaseModel):
    api_key: str = Field(min_length=1)
    model: str = Field(default=DEFAULT_CLAUDE_MODEL, min_length=1, max_length=64)


class UserRequestCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)


class UserRequestRead(BaseModel):
    id: uuid.UUID
    requester_email: str
    prompt: str
    response: str | None
    status: str
    error_message: str | None
    created_at: datetime
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class UserRequestListResponse(BaseModel):
    items: list[UserRequestRead]
    total: int
    limit: int
    offset: int
