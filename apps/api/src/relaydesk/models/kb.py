import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class KbScope(enum.StrEnum):
    internal = "internal"
    external = "external"


class ArticleStatus(enum.StrEnum):
    draft = "draft"
    ready = "ready"
    published = "published"


class KbCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_categories"
    __table_args__ = (
        UniqueConstraint("workspace_id", "scope", "slug"),
        Index("ix_kb_categories_listing", "workspace_id", "scope", "position"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[KbScope] = mapped_column(
        Enum(
            KbScope,
            name="ck_kb_categories_scope",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KbArticle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_articles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "category_id", "slug"),
        Index("ix_kb_articles_listing", "workspace_id", "category_id", "status"),
        Index("ix_kb_articles_search", "search_vector", postgresql_using="gin"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # RESTRICT: a category cannot be deleted out from under its articles.
    category_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("kb_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    # The ProseMirror document. Structured, never HTML -- see spec D1.
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Extracted on write, so the generated column below stays a pure function
    # of stored columns and search never depends on parsing JSON in SQL.
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(
            ArticleStatus,
            name="ck_kb_articles_status",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ArticleStatus.draft,
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        sa.Computed(
            "to_tsvector('english', title || ' ' || coalesce(body_text, ''))",
            persisted=True,
        ),
        nullable=False,
    )

    category = relationship("KbCategory", lazy="selectin")
    images = relationship("KbImage", lazy="selectin", cascade="all, delete-orphan")


class KbImage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_images"
    __table_args__ = (Index("ix_kb_images_article", "article_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("kb_articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
