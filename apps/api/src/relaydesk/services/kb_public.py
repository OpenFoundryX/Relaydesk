"""The public read surface. Published external articles and nothing else.

Every function here takes a workspace_id resolved from the request's
subdomain and applies the same two predicates -- external scope, published
status -- because this is the code path anonymous visitors reach.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbImage, KbScope
from relaydesk.services import blobs, kb_articles, kb_images

# The two predicates that define "public", in one place. `_visible()` below
# applies them directly to a query; `search()` translates them into the
# keyword arguments `kb_articles.search` understands. Nothing else in this
# module should spell out `KbScope.external` or `ArticleStatus.published`
# again -- that would be the same definition stated twice, free to drift.
PUBLIC_SCOPE = KbScope.external
PUBLIC_STATUS = ArticleStatus.published


def _visible(statement):
    """The two predicates that define 'public'. Applied by every query here."""
    return statement.where(
        KbCategory.scope == PUBLIC_SCOPE,
        KbArticle.status == PUBLIC_STATUS,
    )


async def _tree(
    session: AsyncSession, workspace_id: uuid.UUID
) -> tuple[list[KbCategory], dict[uuid.UUID | None, list[KbCategory]]]:
    """Every public category in the workspace, plus a parent -> children map.

    Read whole rather than walked with a recursive CTE. A help centre's
    categories number in the tens even when its articles number in the
    thousands, and depth is capped at three, so the tree fits in one round
    trip and every question below is then a dictionary lookup instead of
    another query.
    """
    rows = await session.scalars(
        sa.select(KbCategory)
        .where(
            KbCategory.workspace_id == workspace_id,
            KbCategory.scope == PUBLIC_SCOPE,
        )
        .order_by(KbCategory.position, KbCategory.name)
    )
    categories = list(rows)
    children: dict[uuid.UUID | None, list[KbCategory]] = {}
    for category in categories:
        children.setdefault(category.parent_id, []).append(category)
    return categories, children


async def _published_counts(
    session: AsyncSession, workspace_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    """How many published articles sit *directly* in each category."""
    rows = await session.execute(
        _visible(
            sa.select(KbArticle.category_id, sa.func.count())
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbCategory.workspace_id == workspace_id,
            )
        ).group_by(KbArticle.category_id)
    )
    return {category_id: int(n) for category_id, n in rows.all()}


def _subtree_count(
    category: KbCategory,
    children: dict[uuid.UUID | None, list[KbCategory]],
    direct: dict[uuid.UUID, int],
) -> int:
    """A category's own published articles plus every descendant's.

    This is the number on a collection's card, and it is also what decides
    whether the card appears at all -- see `roots`.
    """
    return direct.get(category.id, 0) + sum(
        _subtree_count(child, children, direct)
        for child in children.get(category.id, [])
    )


async def roots(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[KbCategory, int]]:
    """The help site's front page: root collections and their article counts.

    A collection whose whole subtree has nothing published is omitted, the
    way the flat index has always omitted empty categories. Counting only
    its direct articles would leave a card whose every link is a 404.
    """
    _, children = await _tree(session, workspace_id)
    direct = await _published_counts(session, workspace_id)
    counted = (
        (category, _subtree_count(category, children, direct))
        for category in children.get(None, [])
    )
    return [(category, n) for category, n in counted if n]


@dataclass(frozen=True)
class CategoryNode:
    """A collection or section page: what it is, where it sits, what it holds."""

    category: KbCategory
    #: Root first, excluding the category itself. The breadcrumb.
    ancestors: list[KbCategory]
    #: Child collections with their subtree counts -- the "7 articles" rows.
    collections: list[tuple[KbCategory, int]]
    #: Published articles sitting directly in this category, not in a child.
    articles: list[KbArticle]


@dataclass(frozen=True)
class ArticleNode:
    """An article page: the article and the categories above it."""

    article: KbArticle
    ancestors: list[KbCategory]


async def _direct_articles(
    session: AsyncSession, workspace_id: uuid.UUID, category_id: uuid.UUID
) -> list[KbArticle]:
    rows = await session.scalars(
        _visible(
            sa.select(KbArticle)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbArticle.category_id == category_id,
            )
        ).order_by(KbArticle.title)
    )
    return list(rows)


def _ancestors_of(
    category_id: uuid.UUID, by_id: dict[uuid.UUID, KbCategory]
) -> list[KbCategory]:
    """The chain from the root down to and including `category_id`."""
    chain: list[KbCategory] = []
    current = by_id.get(category_id)
    while current is not None:
        chain.append(current)
        current = by_id.get(current.parent_id) if current.parent_id else None
    return list(reversed(chain))


async def _unique_article(
    session: AsyncSession, workspace_id: uuid.UUID, slug: str
) -> KbArticle | None:
    """The one published article with this slug, or nothing.

    Two of them is nothing, not a coin toss: slugs are unique among
    siblings, so several sections may each hold a "refunds", and picking
    one would answer a question the caller did not ask.
    """
    rows = (
        await session.scalars(
            _visible(
                sa.select(KbArticle)
                .join(KbCategory, KbCategory.id == KbArticle.category_id)
                .where(
                    KbArticle.workspace_id == workspace_id,
                    KbCategory.workspace_id == workspace_id,
                    KbArticle.slug == slug,
                )
            ).limit(2)
        )
    ).all()
    return rows[0] if len(rows) == 1 else None


async def resolve(
    session: AsyncSession, workspace_id: uuid.UUID, path: Sequence[str]
) -> CategoryNode | ArticleNode:
    """Turn a help-site path into the page it names.

    The path is category slugs, except that the last segment may instead be
    an article. One function rather than two endpoints because the caller --
    a single catch-all route -- cannot know which it is holding until the
    walk is done.

    Everything unresolvable raises `NotFound`, with no distinction between a
    draft, an internal category, another workspace's, and a slug that never
    existed. Telling them apart would say which ones exist.
    """
    if not path:
        raise NotFound("No such page.")

    categories, children = await _tree(session, workspace_id)
    direct = await _published_counts(session, workspace_id)
    by_id = {category.id: category for category in categories}

    ancestors: list[KbCategory] = []
    current: KbCategory | None = None
    for index, segment in enumerate(path):
        siblings = children.get(current.id if current else None, [])
        match = next((c for c in siblings if c.slug == segment), None)
        if match is None:
            # Only the final segment may be an article; anything else that
            # fails to match a category ends the walk.
            if current is not None and index == len(path) - 1:
                found = await session.scalar(
                    _visible(
                        sa.select(KbArticle)
                        .join(KbCategory, KbCategory.id == KbArticle.category_id)
                        .where(
                            KbArticle.workspace_id == workspace_id,
                            KbArticle.category_id == current.id,
                            KbArticle.slug == segment,
                        )
                    )
                )
                if found is not None:
                    # `current` is the article's own category, which the
                    # walk has not appended yet -- it only appends the
                    # previous one when a further category matches.
                    return ArticleNode(
                        article=found, ancestors=[*ancestors, current]
                    )
                # The article is not here, but it may have been moved. Every
                # link the flat KB ever published is /{category}/{slug}, and
                # putting that article into a section would break all of
                # them. So fall back to the slug alone -- scoped to this
                # workspace, and only when it is unambiguous, because
                # sibling-unique slugs mean two sections may hold the same
                # one and a guess between them would be a wrong answer
                # rather than a missing one.
                moved = await _unique_article(session, workspace_id, segment)
                if moved is not None:
                    return ArticleNode(
                        article=moved,
                        ancestors=_ancestors_of(moved.category_id, by_id),
                    )
            raise NotFound("No such page.")
        if current is not None:
            ancestors.append(current)
        current = match

    assert current is not None  # the empty path is refused above
    return CategoryNode(
        category=current,
        ancestors=ancestors,
        collections=[
            (child, _subtree_count(child, children, direct))
            for child in children.get(current.id, [])
            if _subtree_count(child, children, direct)
        ],
        articles=await _direct_articles(session, workspace_id, current.id),
    )


async def search(
    session: AsyncSession, workspace_id: uuid.UUID, query: str
) -> list[KbArticle]:
    return await kb_articles.search(
        session, workspace_id, query, scope=PUBLIC_SCOPE, status=PUBLIC_STATUS
    )


async def image(
    session: AsyncSession, workspace_id: uuid.UUID, image_id: uuid.UUID
) -> tuple[KbImage, bytes]:
    """An image inherits its article's visibility.

    Without this join an unpublished article's screenshots are readable by
    anyone who guesses an id -- the article hidden, its pictures not.
    """
    row = await session.scalar(
        _visible(
            sa.select(KbImage)
            .join(KbArticle, KbArticle.id == KbImage.article_id)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbImage.id == image_id,
                KbImage.workspace_id == workspace_id,
                KbArticle.workspace_id == workspace_id,
                KbCategory.workspace_id == workspace_id,
            )
        )
    )
    if row is None:
        raise NotFound("No such image.")
    return row, blobs.read(kb_images.storage_root(), workspace_id, row.sha256)
