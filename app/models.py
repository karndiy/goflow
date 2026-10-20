"""Aggregates all ORM models so Base.metadata is fully populated for Alembic autogenerate."""

from app.modules.accounts.models import OAuthToken, SocialAccount
from app.modules.auth.models import User, Workspace, WorkspaceMember
from app.modules.content.models import Content, ContentVariant, ContentVariantMedia, MediaAsset
from app.modules.publishing.models import PublishAttempt, PublishingJob

__all__ = [
    "User",
    "Workspace",
    "WorkspaceMember",
    "SocialAccount",
    "OAuthToken",
    "Content",
    "ContentVariant",
    "MediaAsset",
    "ContentVariantMedia",
    "PublishingJob",
    "PublishAttempt",
]
