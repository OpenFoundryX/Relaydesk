"""Anonymous, read-only routes for the customer-facing portal.

Everything here is reachable without a session by design -- a published
knowledge base is public. That makes the rule for this module simple and
absolute: return display information and published content, never anything
about tickets, members, plans, or usage.
"""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Response

from relaydesk.api.deps import DbSession
from relaydesk.errors import NotFound
from relaydesk.models.kb import KbArticle
from relaydesk.models.workspace import Workspace
from relaydesk.schemas.kb import (
    PublicArticleOut,
    PublicArticleSummary,
    PublicCategoryOut,
    PublicWorkspaceOut,
)
from relaydesk.services import kb_public
from relaydesk.services.workspaces import RESERVED_SLUGS

router = APIRouter()


async def resolve_workspace(session: DbSession, slug: str) -> Workspace:
    """Shared by every public route. A reserved label is a 404, not a lookup."""
    if slug.lower() in RESERVED_SLUGS:
        raise NotFound("No such workspace.")
    workspace = await session.scalar(
        sa.select(Workspace).where(Workspace.slug == slug.lower())
    )
    if workspace is None:
        raise NotFound("No such workspace.")
    return workspace


@router.get("/workspaces/{slug}", response_model=PublicWorkspaceOut)
async def read_workspace(slug: str, session: DbSession) -> PublicWorkspaceOut:
    workspace = await resolve_workspace(session, slug)
    return PublicWorkspaceOut(name=workspace.name, monogram=workspace.monogram)


def _article_summary(article: KbArticle) -> PublicArticleSummary:
    return PublicArticleSummary(
        id=str(article.id),
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
    )


def _article_out(article: KbArticle) -> PublicArticleOut:
    return PublicArticleOut(
        id=str(article.id),
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
        doc=article.doc,
        published_at=article.published_at,
    )


@router.get("/{slug}/kb", response_model=list[PublicCategoryOut])
async def read_kb_index(slug: str, session: DbSession) -> list[PublicCategoryOut]:
    workspace = await resolve_workspace(session, slug)
    rows = await kb_public.index(session, workspace.id)
    return [
        PublicCategoryOut(
            id=str(category.id),
            name=category.name,
            slug=category.slug,
            articles=[_article_summary(article) for article in articles],
        )
        for category, articles in rows
    ]


@router.get("/{slug}/kb/search", response_model=list[PublicArticleSummary])
async def search_kb(
    slug: str, session: DbSession, q: str = ""
) -> list[PublicArticleSummary]:
    workspace = await resolve_workspace(session, slug)
    articles = await kb_public.search(session, workspace.id, q)
    return [_article_summary(article) for article in articles]


@router.get("/{slug}/kb/images/{image_id}")
async def read_kb_image(slug: str, image_id: uuid.UUID, session: DbSession) -> Response:
    workspace = await resolve_workspace(session, slug)
    row, content = await kb_public.image(session, workspace.id, image_id)
    return Response(
        content=content,
        media_type=row.content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/{slug}/kb/{category_slug}/{article_slug}", response_model=PublicArticleOut
)
async def read_kb_article(
    slug: str, category_slug: str, article_slug: str, session: DbSession
) -> PublicArticleOut:
    workspace = await resolve_workspace(session, slug)
    article = await kb_public.article(
        session, workspace.id, category_slug, article_slug
    )
    return _article_out(article)
