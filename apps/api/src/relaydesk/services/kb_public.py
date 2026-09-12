"""The public read surface. Published external articles and nothing else.

Every function here takes a workspace_id resolved from the request's
subdomain and applies the same two predicates -- external scope, published
status -- because this is the code path anonymous visitors reach.
"""

import functools
import re
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
class Section:
    """A child collection together with the rows its card lists.

    The page draws one card per section, and each card lists that section's
    own articles and sub-collections. Fetching those a card at a time would
    be a request per section for something the tree already in hand can
    answer, so they come down with the page.
    """

    category: KbCategory
    #: Everything published beneath it -- what its own card would say.
    article_count: int
    #: Sub-collections of this section, with their counts. Rows, not cards.
    collections: list[tuple[KbCategory, int]]
    #: Published articles directly in this section. The other kind of row.
    articles: list[KbArticle]


@dataclass(frozen=True)
class CategoryNode:
    """A collection or section page: what it is, where it sits, what it holds."""

    category: KbCategory
    #: Root first, excluding the category itself. The breadcrumb.
    ancestors: list[KbCategory]
    #: The cards on this page: one per child collection, each with its rows.
    sections: list[Section]
    #: Published articles sitting directly here rather than in a section.
    articles: list[KbArticle]


@dataclass(frozen=True)
class ArticleNode:
    """An article page: the article and the categories above it."""

    article: KbArticle
    ancestors: list[KbCategory]


async def _direct_articles(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, list[KbArticle]]:
    """The published articles sitting directly in each of these categories.

    Takes the whole set a page needs -- the category itself and every
    section on it -- so one query answers the page rather than one per card.
    """
    if not category_ids:
        return {}
    rows = await session.scalars(
        _visible(
            sa.select(KbArticle)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbArticle.category_id.in_(category_ids),
            )
        ).order_by(KbArticle.title)
    )
    grouped: dict[uuid.UUID, list[KbArticle]] = {}
    for article in rows:
        grouped.setdefault(article.category_id, []).append(article)
    return grouped


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


async def count(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    """How many published articles this workspace has, without building them.

    `bootstrap()` (`api/widget.py`) is the one endpoint every widget panel
    open hits, and it needs only this number compared against zero -- it
    used to call `searchable()` and take `len(...)`, which built every
    published article's row *and* walked the category tree for each one's
    ancestor chain, purely to throw all of it away but a count.

    Built on the same `_visible()` predicate as `searchable()`, joined to
    `KbCategory` the same explicit way, so "the knowledge base is empty"
    still means exactly "search would find nothing", by construction rather
    than by two queries agreeing. An earlier attempt at a count function was
    rejected for filtering on `KbCategory` while selecting only from
    `KbArticle` with no join between them -- a cartesian product. That was
    wrong about the join, not about the idea of a count; this one joins the
    way every other query in this module does.
    """
    total = await session.scalar(
        _visible(
            sa.select(sa.func.count(KbArticle.id))
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbCategory.workspace_id == workspace_id,
            )
        )
    )
    return int(total or 0)


async def searchable(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[KbArticle, list[KbCategory]]]:
    """Every published article, with the categories above it.

    The help site's instant search scores this in the browser, so it is
    read once per visitor instead of queried per keystroke. That makes the
    visibility rule matter more here than anywhere else on this module: the
    result is handed to anonymous visitors wholesale, and a draft that
    reached it would publish an unfinished article's title and blurb to
    everyone without ever rendering the article -- a leak with nothing on
    screen to give it away. It is the same `_visible()` predicate as every
    other read here, which is the point: there is one definition of public
    and this is not allowed its own.

    Bodies are deliberately absent. They are what makes a knowledge base
    too large to ship, and the server's full-text search over them is what
    the results page is for.
    """
    rows = await session.scalars(
        _visible(
            sa.select(KbArticle)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbCategory.workspace_id == workspace_id,
            )
        ).order_by(KbArticle.title)
    )
    articles = list(rows)
    ancestors = await paths_for(session, workspace_id, articles)
    return [(article, ancestors.get(article.id, [])) for article in articles]


async def paths_for(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    articles: Sequence[KbArticle],
) -> dict[uuid.UUID, list[KbCategory]]:
    """Where each of these articles lives, as a chain of categories.

    Search hands back articles with no idea where they sit, and a caller
    holding one cannot rebuild its link from the slug alone once categories
    nest -- it would have to fetch and walk the whole index. One tree read
    answers it for the whole result set.
    """
    categories, _ = await _tree(session, workspace_id)
    by_id = {category.id: category for category in categories}
    return {
        article.id: _ancestors_of(article.category_id, by_id)
        for article in articles
    }


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

    # A section with nothing published anywhere beneath it is dropped for
    # the same reason an empty collection never reaches the front page: its
    # card would be a heading over a set of links that all 404.
    sections = [
        (child, _subtree_count(child, children, direct))
        for child in children.get(current.id, [])
    ]
    sections = [(child, n) for child, n in sections if n]

    by_category = await _direct_articles(
        session, workspace_id, [current.id, *(child.id for child, _ in sections)]
    )

    return CategoryNode(
        category=current,
        ancestors=ancestors,
        sections=[
            Section(
                category=child,
                article_count=count,
                collections=[
                    (grandchild, _subtree_count(grandchild, children, direct))
                    for grandchild in children.get(child.id, [])
                    if _subtree_count(grandchild, children, direct)
                ],
                articles=by_category.get(child.id, []),
            )
            for child, count in sections
        ],
        articles=by_category.get(current.id, []),
    )


async def search(
    session: AsyncSession, workspace_id: uuid.UUID, query: str
) -> list[KbArticle]:
    return await kb_articles.search(
        session, workspace_id, query, scope=PUBLIC_SCOPE, status=PUBLIC_STATUS
    )


def _disjunctive_tsquery(question: str):
    """A tsquery matching an article that shares *any* significant word.

    ``kb_articles.search`` builds ``websearch_to_tsquery``, which ANDs
    every lexeme together -- correct for a search box, where a caller
    typing several words means all of them, wrong for a whole sentence
    handed to it whole, where most of the words are grammar rather than
    intent. This instead builds one ``plainto_tsquery`` per token and ORs
    them with the ``||`` tsquery operator, so a question matches an
    article that contains any one of its significant words, not all.

    ``plainto_tsquery`` on a single stop word (or on no word at all) is
    Postgres' own empty tsquery, and ORing an empty tsquery in changes
    nothing (``'' || x`` is ``x``). A question made entirely of stop
    words therefore reduces to the empty tsquery, and ``@@`` never
    matches an empty tsquery against anything -- the caller gets ``[]``,
    not everything.

    Returns ``None`` when the question has no word characters at all, so
    the caller can skip the query rather than run one that can only find
    nothing.
    """
    tokens = re.findall(r"\w+", question)
    if not tokens:
        return None
    return functools.reduce(
        lambda acc, token: acc.op("||")(sa.func.plainto_tsquery("english", token)),
        tokens[1:],
        sa.func.plainto_tsquery("english", tokens[0]),
    )


async def search_any(
    session: AsyncSession, workspace_id: uuid.UUID, question: str, *, limit: int = 5
) -> list[KbArticle]:
    """Published external articles sharing any significant word with the question.

    Ranked best first.

    For ``ai_retrieval.retrieve`` only. ``search()`` above is
    ``kb_articles.search`` with this module's two visibility predicates
    fixed in, and it is the help site's and the console's search box --
    its all-terms-must-match query is correct there, where a caller types
    keywords. A visitor's question is prose, and ANDing every one of its
    words returns nothing for most ordinary phrasing (see
    ``_disjunctive_tsquery``). This runs that disjunctive, ranked query
    instead, through the exact same ``_visible()`` this module applies
    everywhere else -- published status, external scope, nothing else --
    rather than adding a second mode to ``kb_articles.search`` and risking
    the help site inheriting a predicate meant only for retrieval.

    An empty result means no published external article in this
    workspace shares a significant word with the question -- including a
    question that is only stop words, or empty.
    """
    tsquery = _disjunctive_tsquery(question)
    if tsquery is None:
        return []
    rows = await session.scalars(
        _visible(
            sa.select(KbArticle)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbCategory.workspace_id == workspace_id,
                KbArticle.search_vector.op("@@")(tsquery),
            )
        )
        .order_by(sa.func.ts_rank(KbArticle.search_vector, tsquery).desc())
        .limit(limit)
    )
    return list(rows.all())


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
