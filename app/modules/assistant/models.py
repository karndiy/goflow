import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin

REQUEST_STATUSES = ("pending", "answered", "failed")
DEFAULT_CLAUDE_MODEL = "claude-opus-5"


class AISettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-level Anthropic API credentials for the in-app 'ask Claude' feature."""

    __tablename__ = "ai_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    encrypted_api_key: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default=DEFAULT_CLAUDE_MODEL)


class UserRequest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_requests"
    __table_args__ = (Index("ix_user_requests_workspace_created", "workspace_id", "created_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    requester_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requester_email: Mapped[str] = mapped_column(String(320), nullable=False)
    prompt: Mapped[str] = mapped_column(String, nullable=False)
    response: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
