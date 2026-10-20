import uuid
from datetime import datetime

from pydantic import BaseModel, Field

SUPPORTED_CREDENTIAL_PLATFORMS = ("facebook", "tiktok")


class ConnectResponse(BaseModel):
    authorization_url: str


class PlatformCredentialRead(BaseModel):
    platform: str
    app_id: str
    has_secret: bool
    updated_at: datetime


class PlatformCredentialWrite(BaseModel):
    app_id: str = Field(min_length=1, max_length=255)
    app_secret: str = Field(min_length=1)


class SocialAccountRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    platform: str
    external_account_id: str
    account_name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
