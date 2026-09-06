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


async def create(
    session: AsyncSession, workspace_id: uuid.UUID, name: str, scope: KbScope
) -> KbCategory:
    slug = slugify(name)
    if slug in RESERVED_CATEGORY_SLUGS:
        raise Invalid("That category name collides with a reserved KB route.")
    existing = await session.scalar(
        sa.select(KbCategory.id).where(
            KbCategory.workspace_id == workspace_id,
            KbCategory.scope == scope,
            KbCategory.slug == slug,
        )
    )
    if existing is not None:
        raise Conflict("A category with that name already exists.")

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
    await session.delete(category)
    await session.flush()
