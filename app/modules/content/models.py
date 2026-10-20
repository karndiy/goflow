import uuid

from sqlalchemy import JSON, BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin

CONTENT_STATUSES = ("draft", "scheduled", "publishing", "published", "partial_failure", "failed")
MEDIA_TYPES = ("none", "image", "video", "carousel")


class Content(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    variants: Mapped[list["ContentVariant"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )


class ContentVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_variants"
    __table_args__ = (UniqueConstraint("content_id", "platform", name="uq_content_variant"),)

    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False, default="")
    media_type: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    content: Mapped[Content] = relationship(back_populates="variants")
    media_links: Mapped[list["ContentVariantMedia"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_assets"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ContentVariantMedia(Base):
    __tablename__ = "content_variant_media"

    content_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_variants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    variant: Mapped[ContentVariant] = relationship(back_populates="media_links")
