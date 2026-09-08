"""kb category tree

Turns the flat ``kb_categories`` list into the three-level tree the help
site renders: collection -> section -> sub-section, with articles hanging
off any level.

Purely additive. Every existing category is already exactly a root
collection, so it takes ``parent_id NULL, depth 0`` and the public site
renders identically the moment this lands -- there is no backfill and no
window where the KB is half-migrated.

``depth`` is stored rather than walked. That buys two invariants for the
price of one column: the three-level cap becomes a CHECK the database
enforces, and cycles become impossible, because a cycle would require
``a.depth = b.depth + 1`` and ``b.depth = a.depth + 1`` to hold at once.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-08 19:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_categories", sa.Column("parent_id", sa.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "kb_categories",
        sa.Column("depth", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    # The card face: a blurb and an icon name. Empty rather than NULL, so
    # the help site has one rendering path instead of two.
    op.add_column(
        "kb_categories",
        sa.Column(
            "description", sa.String(length=400), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "kb_categories",
        sa.Column("icon", sa.String(length=40), nullable=False, server_default=""),
    )
    # The parent FK is composite on purpose. Referencing (id, workspace_id,
    # scope) rather than id alone means a category can only ever be nested
    # under one in the same workspace *and* the same scope -- an internal
    # section under an external collection, which would publish staff-only
    # articles to the help site, becomes unrepresentable rather than merely
    # rejected in the service. A NULL parent_id satisfies it (MATCH
    # SIMPLE), so root collections are unaffected.
    #
    # RESTRICT matches kb_articles.category_id: a collection is never
    # deleted out from under what it holds.
    op.create_unique_constraint(
        "uq_kb_categories_identity", "kb_categories", ["id", "workspace_id", "scope"]
    )
    op.create_foreign_key(
        "fk_kb_categories_parent",
        "kb_categories",
        "kb_categories",
        ["parent_id", "workspace_id", "scope"],
        ["id", "workspace_id", "scope"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_kb_categories_depth", "kb_categories", "depth BETWEEN 0 AND 2"
    )
    # Slugs become unique among siblings rather than across the whole
    # scope, so each collection can have its own "Getting started" without
    # the second one carrying a "-2" in its URL forever.
    #
    # NULLS NOT DISTINCT (Postgres 15+) is the load-bearing part: root
    # collections all have parent_id NULL, and under the default NULLS
    # DISTINCT rule Postgres would consider every one of those rows unique
    # regardless of slug -- two root collections could then share a slug
    # and make /help/{slug} ambiguous, with the constraint looking like it
    # was enforcing something.
    op.drop_constraint(
        "kb_categories_workspace_id_scope_slug_key", "kb_categories", type_="unique"
    )
    op.execute(
        "ALTER TABLE kb_categories"
        " ADD CONSTRAINT uq_kb_categories_sibling_slug"
        " UNIQUE NULLS NOT DISTINCT (workspace_id, scope, parent_id, slug)"
    )
    # Siblings are listed together now, so the listing index leads with the
    # parent. Dropped and recreated rather than altered -- Postgres has no
    # ALTER INDEX for column lists.
    op.drop_index("ix_kb_categories_listing", table_name="kb_categories")
    op.create_index(
        "ix_kb_categories_listing",
        "kb_categories",
        ["workspace_id", "scope", "parent_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_kb_categories_listing", table_name="kb_categories")
    op.create_index(
        "ix_kb_categories_listing",
        "kb_categories",
        ["workspace_id", "scope", "position"],
    )
    op.drop_constraint(
        "uq_kb_categories_sibling_slug", "kb_categories", type_="unique"
    )
    op.create_unique_constraint(
        "kb_categories_workspace_id_scope_slug_key",
        "kb_categories",
        ["workspace_id", "scope", "slug"],
    )
    op.drop_constraint("ck_kb_categories_depth", "kb_categories", type_="check")
    op.drop_constraint("fk_kb_categories_parent", "kb_categories", type_="foreignkey")
    op.drop_constraint("uq_kb_categories_identity", "kb_categories", type_="unique")
    op.drop_column("kb_categories", "icon")
    op.drop_column("kb_categories", "description")
    op.drop_column("kb_categories", "depth")
    op.drop_column("kb_categories", "parent_id")
