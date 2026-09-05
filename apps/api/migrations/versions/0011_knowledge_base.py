"""knowledge base

Adds the tables the knowledge base slice reads and writes: categories,
articles, and article images.

Two things autogenerate gets wrong for a generated ``tsvector`` column and
its index, confirmed here rather than left to guesswork:

- ``kb_articles.search_vector`` must carry the same ``sa.Computed(...,
  persisted=True)`` expression as the model, so Postgres derives it from
  ``title`` and ``body_text`` rather than the migration creating a plain
  column nothing ever populates.
- ``ix_kb_articles_search`` must be built with ``postgresql_using="gin"``. A
  default btree index on a ``tsvector`` column is not an error -- it is
  simply never used by a ``@@`` query, so search would silently fall back to
  a sequential scan.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-05 10:55:11.838638
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kb_categories",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "scope",
            sa.Enum(
                "internal",
                "external",
                name="ck_kb_categories_scope",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "scope", "slug"),
    )
    op.create_index(
        "ix_kb_categories_listing",
        "kb_categories",
        ["workspace_id", "scope", "position"],
        unique=False,
    )
    op.create_index(
        op.f("ix_kb_categories_workspace_id"),
        "kb_categories",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "kb_articles",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("excerpt", sa.String(length=400), nullable=False),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "ready",
                "published",
                name="ck_kb_articles_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', title || ' ' || coalesce(body_text, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["kb_categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "category_id", "slug"),
    )
    op.create_index(
        "ix_kb_articles_listing",
        "kb_articles",
        ["workspace_id", "category_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_kb_articles_search",
        "kb_articles",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_kb_articles_workspace_id"),
        "kb_articles",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "kb_images",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["kb_articles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kb_images_article", "kb_images", ["article_id"], unique=False
    )
    op.create_index(
        op.f("ix_kb_images_workspace_id"),
        "kb_images",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_kb_images_workspace_id"), table_name="kb_images")
    op.drop_index("ix_kb_images_article", table_name="kb_images")
    op.drop_table("kb_images")
    op.drop_index(op.f("ix_kb_articles_workspace_id"), table_name="kb_articles")
    op.drop_index(
        "ix_kb_articles_search",
        table_name="kb_articles",
        postgresql_using="gin",
    )
    op.drop_index("ix_kb_articles_listing", table_name="kb_articles")
    op.drop_table("kb_articles")
    op.drop_index(
        op.f("ix_kb_categories_workspace_id"), table_name="kb_categories"
    )
    op.drop_index("ix_kb_categories_listing", table_name="kb_categories")
    op.drop_table("kb_categories")
