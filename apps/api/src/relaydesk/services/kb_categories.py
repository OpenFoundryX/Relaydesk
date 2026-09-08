import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.models.kb import KbArticle, KbCategory, KbScope
from relaydesk.services.kb_text import slugify

# These collide with the public routes' fixed path segments --
# `/kb/images/{id}` and `/kb/search` -- both of which sit at the same depth
# as `/kb/{category_slug}/{article_slug}`. A category slugifying to one of
# these would have every one of its articles swallowed by the wrong route.
RESERVED_CATEGORY_SLUGS = frozenset({"images", "search"})

# The deepest `depth` a category may hold: 0 is a root collection, so this
# is three container levels, which is what the help site renders.
MAX_DEPTH = 2

# The icon a collection may wear on its card. These are Lucide names, and
# both the console picker and the help site resolve them against a static
# map -- a name outside this set renders as nothing at all, and the hole
# would appear on a customer's screen rather than the author's. Stored as a
# name rather than markup so an author can never put SVG into a page.
CATEGORY_ICONS = frozenset(
    {
        "book-open",
        "rocket",
        "credit-card",
        "settings",
        "users",
        "mail",
        "plug",
        "shield",
        "life-buoy",
        "smartphone",
        "chart-bar",
        "folder",
    }
)


async def create(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    scope: KbScope,
    *,
    parent_id: uuid.UUID | None = None,
    description: str = "",
    icon: str = "",
) -> KbCategory:
    slug = slugify(name)
    if icon and icon not in CATEGORY_ICONS:
        raise Invalid("That is not one of the available category icons.")
    if slug in RESERVED_CATEGORY_SLUGS:
        raise Invalid("That category name collides with a reserved KB route.")
    # Among siblings, not across the workspace. Every collection wants its
    # own "Getting started", and the alternative -- "getting-started-2" --
    # would be in that section's URL for good.
    existing = await session.scalar(
        sa.select(KbCategory.id).where(
            KbCategory.workspace_id == workspace_id,
            KbCategory.scope == scope,
            KbCategory.parent_id.is_(parent_id)
            if parent_id is None
            else KbCategory.parent_id == parent_id,
            KbCategory.slug == slug,
        )
    )
    if existing is not None:
        raise Conflict("A category with that name already exists here.")

    depth = 0
    if parent_id is not None:
        parent = await _get(session, workspace_id, parent_id)
        # Internal and external are separate namespaces, and nesting across
        # them would hang staff-only articles under a collection the public
        # help site walks. Refused here and made impossible by the composite
        # FK on (parent_id, workspace_id, scope) -- see migration 0019.
        if parent.scope is not scope:
            raise Invalid("A category cannot be nested under another scope.")
        depth = parent.depth + 1
        # The same rule the `ck_kb_categories_depth` CHECK enforces, stated
        # here so a caller gets a 400 explaining itself rather than the 500
        # an IntegrityError turns into. The constraint stays as the
        # backstop: this branch is reachable only through the service, and
        # the invariant belongs to the data, not to this function.
        if depth > MAX_DEPTH:
            raise Invalid("A category can be nested three levels deep at most.")

    highest = await session.scalar(
        sa.select(sa.func.max(KbCategory.position)).where(
            KbCategory.workspace_id == workspace_id, KbCategory.scope == scope
        )
    )
    category = KbCategory(
        workspace_id=workspace_id,
        scope=scope,
        name=name.strip(),
        slug=slug,
        position=0 if highest is None else highest + 1,
        parent_id=parent_id,
        depth=depth,
        description=description.strip(),
        icon=icon,
    )
    session.add(category)
    await session.flush()
    return category


async def list_for(
    session: AsyncSession, workspace_id: uuid.UUID, scope: KbScope
) -> list[tuple[KbCategory, int]]:
    """Categories in display order, each with how many articles it holds.

    The count is every article regardless of status -- this is the console.
    The public index counts published only, and lives in kb_public.
    """
    counts = (
        sa.select(KbArticle.category_id, sa.func.count().label("n"))
        .where(KbArticle.workspace_id == workspace_id)
        .group_by(KbArticle.category_id)
        .subquery()
    )
    rows = await session.execute(
        sa.select(KbCategory, sa.func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.category_id == KbCategory.id)
        .where(KbCategory.workspace_id == workspace_id, KbCategory.scope == scope)
        .order_by(KbCategory.position, KbCategory.name)
    )
    return [(category, int(n)) for category, n in rows.all()]


async def _get(
    session: AsyncSession, workspace_id: uuid.UUID, category_id: uuid.UUID
) -> KbCategory:
    category = await session.scalar(
        sa.select(KbCategory).where(
            KbCategory.id == category_id, KbCategory.workspace_id == workspace_id
        )
    )
    if category is None:
        raise NotFound("That category does not exist.")
    return category


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    name: str | None = None,
    position: int | None = None,
) -> KbCategory:
    category = await _get(session, workspace_id, category_id)
    if name is not None:
        # The slug is deliberately not recomputed: it is the public URL, and
        # renaming a category must not break a link someone bookmarked.
        category.name = name.strip()
    if position is not None:
        category.position = position
    await session.flush()
    return category


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    category = await _get(session, workspace_id, category_id)
    held = await session.scalar(
        sa.select(sa.func.count())
        .select_from(KbArticle)
        .where(
            KbArticle.category_id == category.id,
            KbArticle.workspace_id == workspace_id,
        )
    )
    if held:
        raise Conflict("That category still holds articles. Move or delete them first.")
    children = await session.scalar(
        sa.select(sa.func.count())
        .select_from(KbCategory)
        .where(
            KbCategory.parent_id == category.id,
            KbCategory.workspace_id == workspace_id,
        )
    )
    if children:
        raise Conflict(
            "That category still holds sub-categories. Move or delete them first."
        )
    await session.delete(category)
    await session.flush()
