import uuid
from datetime import datetime

from pydantic import BaseModel


class SocialAccountRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    platform: str
    external_account_id: str
    account_name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
