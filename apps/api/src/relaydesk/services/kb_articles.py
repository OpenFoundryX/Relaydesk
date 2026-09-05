import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope
from relaydesk.models.user import User
from relaydesk.services.kb_text import derive_excerpt, extract_text, slugify

EMPTY_DOC: dict = {"type": "doc", "content": []}


async def _category(
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


async def _unique_slug(
    session: AsyncSession, category_id: uuid.UUID, title: str
) -> str:
    """Two articles may share a title; their URLs cannot."""
    base = slugify(title)
    taken = set(
        (
            await session.scalars(
                sa.select(KbArticle.slug).where(KbArticle.category_id == category_id)
            )
        ).all()
    )
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


async def create(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    title: str,
    author: User | None,
) -> KbArticle:
    category = await _category(session, workspace_id, category_id)
    article = KbArticle(
        workspace_id=workspace_id,
        category_id=category.id,
        title=title.strip(),
        slug=await _unique_slug(session, category.id, title),
        excerpt="",
        doc=EMPTY_DOC,
        body_text="",
        status=ArticleStatus.draft,
        author_user_id=author.id if author else None,
    )
    session.add(article)
    await session.flush()
    return article


async def get(
    session: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID
) -> KbArticle:
    article = await session.scalar(
        sa.select(KbArticle).where(
            KbArticle.id == article_id, KbArticle.workspace_id == workspace_id
        )
    )
    if article is None:
        raise NotFound("That article does not exist.")
    return article


async def list_for(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    scope: KbScope | None = None,
    status: ArticleStatus | None = None,
) -> list[KbArticle]:
    query = (
        sa.select(KbArticle)
        .join(KbCategory, KbCategory.id == KbArticle.category_id)
        .where(KbArticle.workspace_id == workspace_id)
        .order_by(KbCategory.position, KbArticle.title)
    )
    if scope is not None:
        query = query.where(KbCategory.scope == scope)
    if status is not None:
        query = query.where(KbArticle.status == status)
    return list((await session.scalars(query)).all())


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    article_id: uuid.UUID,
    *,
    title: str | None = None,
    excerpt: str | None = None,
    doc: dict | None = None,
    category_id: uuid.UUID | None = None,
) -> KbArticle:
    article = await get(session, workspace_id, article_id)
    current = await _category(session, workspace_id, article.category_id)

    if category_id is not None and category_id != article.category_id:
        target = await _category(session, workspace_id, category_id)
        if target.scope is not current.scope:
            # Scope lives on the category, so this would silently change who
            # can read the article.
            raise Invalid("An article cannot move between internal and external.")
        article.category_id = target.id
        article.slug = await _unique_slug(session, target.id, article.title)

    if title is not None:
        # The slug is deliberately not recomputed -- it is the published URL.
        article.title = title.strip()
    if excerpt is not None:
        article.excerpt = excerpt.strip()[:400]
    if doc is not None:
        article.doc = doc
        article.body_text = extract_text(doc)
        if not article.excerpt:
            article.excerpt = derive_excerpt(article.body_text)

    await session.flush()
    return article


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID
) -> None:
    article = await get(session, workspace_id, article_id)
    await session.delete(article)
    await session.flush()
