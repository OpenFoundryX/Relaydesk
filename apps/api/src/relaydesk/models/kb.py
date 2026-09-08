import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
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
        # Unique among siblings, not across the scope. NULLS NOT DISTINCT
        # is what makes it bite for root collections, whose parent_id is
        # NULL -- see migration 0019.
        UniqueConstraint(
            "workspace_id",
            "scope",
            "parent_id",
            "slug",
            name="uq_kb_categories_sibling_slug",
            postgresql_nulls_not_distinct=True,
        ),
        # The target of the composite parent FK below. Its only job is to
        # give that FK something to reference -- `id` is already the key.
        UniqueConstraint(
            "id", "workspace_id", "scope", name="uq_kb_categories_identity"
        ),
        # Carrying workspace and scope through the FK is what makes a
        # cross-tenant or cross-scope parent unrepresentable rather than
        # merely rejected. NULL parent_id satisfies it (MATCH SIMPLE), so
        # root collections are unaffected.
        ForeignKeyConstraint(
            ["parent_id", "workspace_id", "scope"],
            ["kb_categories.id", "kb_categories.workspace_id", "kb_categories.scope"],
            name="fk_kb_categories_parent",
            ondelete="RESTRICT",
        ),
        CheckConstraint("depth BETWEEN 0 AND 2", name="ck_kb_categories_depth"),
        Index(
            "ix_kb_categories_listing",
            "workspace_id",
            "scope",
            "parent_id",
            "position",
        ),
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
    # The blurb under a collection's title on the help site, and the name
    # of the icon shown beside it. Both default to empty rather than NULL:
    # the card renders the same either way, and a nullable column would put
    # a second branch in every template that touches them.
    description: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    # The tree. A root collection has no parent and sits at depth 0; the
    # deepest a sub-collection may go is 2, which is the three container
    # levels the help site renders. RESTRICT rather than CASCADE, matching
    # the article FK below: a collection is never deleted out from under
    # the sub-collections it holds.
    # No column-level ForeignKey: the real one is composite, declared in
    # __table_args__, and carries scope and workspace with it.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    # Stored rather than walked. Two things fall out of that: the depth cap
    # becomes a CHECK the database enforces, and cycles become impossible
    # -- a cycle would need a.depth = b.depth + 1 and b.depth = a.depth + 1
    # at the same time.
    depth: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)


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
    # Selectin rather than lazy: the help site prints a byline under every
    # article, and a lazy load would be a query per article inside an async
    # session that has no synchronous fallback to do it in.
    author = relationship("User", lazy="selectin")
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
