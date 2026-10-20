"""Aggregates all ORM models so Base.metadata is fully populated for Alembic autogenerate."""

from app.modules.accounts.models import OAuthToken, PlatformCredential, SocialAccount
from app.modules.assistant.models import AISettings, UserRequest
from app.modules.audit.models import AuditLog, Release
from app.modules.auth.models import User, Workspace, WorkspaceMember
from app.modules.content.models import (
    Content,
    ContentGenerationJob,
    ContentVariant,
    ContentVariantMedia,
    MediaAsset,
)
from app.modules.publishing.models import PublishAttempt, PublishingJob

__all__ = [
    "User",
    "Workspace",
    "WorkspaceMember",
    "SocialAccount",
    "OAuthToken",
    "PlatformCredential",
    "Content",
    "ContentVariant",
    "MediaAsset",
    "ContentVariantMedia",
    "PublishingJob",
    "PublishAttempt",
    "AuditLog",
    "Release",
    "AISettings",
    "UserRequest",
    "ContentGenerationJob",
]
