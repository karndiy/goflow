import uuid
from datetime import datetime

from pydantic import BaseModel


class PublishAttemptRead(BaseModel):
    id: uuid.UUID
    attempt_number: int
    status: str
    provider_request_id: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishingJobRead(BaseModel):
    id: uuid.UUID
    content_variant_id: uuid.UUID
    social_account_id: uuid.UUID
    scheduled_at: datetime
    status: str
    external_post_id: str | None
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublishingJobDetailRead(PublishingJobRead):
    publish_attempts: list[PublishAttemptRead]


class JobListResponse(BaseModel):
    items: list[PublishingJobRead]
    total: int
    limit: int
    offset: int


class ScheduleAssignment(BaseModel):
    social_account_id: uuid.UUID
    platform: str
    scheduled_at: datetime


class ScheduleRequest(BaseModel):
    assignments: list[ScheduleAssignment]


class CalendarEntry(BaseModel):
    job_id: uuid.UUID
    content_id: uuid.UUID
    content_title: str
    platform: str
    social_account_id: uuid.UUID
    account_name: str
    scheduled_at: datetime
    status: str
