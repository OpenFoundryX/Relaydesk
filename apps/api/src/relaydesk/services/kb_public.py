"""The public read surface. Published external articles and nothing else.

Every function here takes a workspace_id resolved from the request's
subdomain and applies the same two predicates -- external scope, published
status -- because this is the code path anonymous visitors reach.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbImage, KbScope
from relaydesk.services import blobs, kb_articles, kb_images


def _visible(statement):
    """The two predicates that define 'public'. Applied by every query here."""
    return statement.where(
        KbCategory.scope == KbScope.external,
        KbArticle.status == ArticleStatus.published,
    )


async def index(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[KbCategory, list[KbArticle]]]:
    rows = await session.execute(
        _visible(
            sa.select(KbCategory, KbArticle)
            .join(KbArticle, KbArticle.category_id == KbCategory.id)
            .where(KbCategory.workspace_id == workspace_id)
        ).order_by(KbCategory.position, KbArticle.title)
    )
    grouped: dict[uuid.UUID, tuple[KbCategory, list[KbArticle]]] = {}
    for category, article in rows.all():
        grouped.setdefault(category.id, (category, []))[1].append(article)
    return list(grouped.values())


async def article(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_slug: str,
    article_slug: str,
) -> KbArticle:
    found = await session.scalar(
        _visible(
            sa.select(KbArticle)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbCategory.slug == category_slug,
                KbArticle.slug == article_slug,
            )
        )
    )
    if found is None:
        # 404 rather than 403: confirming an unpublished article exists at a
        # guessable slug is itself a leak.
        raise NotFound("No such article.")
    return found


async def search(
    session: AsyncSession, workspace_id: uuid.UUID, query: str
) -> list[KbArticle]:
    return await kb_articles.search(
        session, workspace_id, query, scope=KbScope.external, published_only=True
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
            )
        )
    )
    if row is None:
        raise NotFound("No such image.")
    return row, blobs.read(kb_images.storage_root(), workspace_id, row.sha256)
