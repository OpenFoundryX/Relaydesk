import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, UploadFile, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.config import get_settings
from relaydesk.errors import Invalid
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope
from relaydesk.schemas.kb import (
    ArticleCreateRequest,
    ArticleOut,
    ArticlePatch,
    ArticleSummary,
    CategoryCreateRequest,
    CategoryOut,
    CategoryPatch,
    ImageOut,
    PublicAuthorOut,
    StatusRequest,
)
from relaydesk.services import kb_articles, kb_categories, kb_images
from relaydesk.services.attachments import INLINE_SAFE_TYPES, safe_content_type

router = APIRouter()


def _parsed_scope(raw: str) -> KbScope:
    try:
        return KbScope(raw)
    except ValueError:
        raise Invalid(f"Unknown scope {raw!r}.") from None


def _parsed_status(raw: str) -> ArticleStatus:
    try:
        return ArticleStatus(raw)
    except ValueError:
        raise Invalid(f"Unknown status {raw!r}.") from None


def _category_out(category: KbCategory, article_count: int) -> CategoryOut:
    return CategoryOut(
        id=str(category.id),
        name=category.name,
        slug=category.slug,
        scope=category.scope.value,
        position=category.position,
        article_count=article_count,
        parent_id=str(category.parent_id) if category.parent_id else None,
        depth=category.depth,
        description=category.description,
        icon=category.icon,
    )


def _article_summary(article: KbArticle) -> ArticleSummary:
    return ArticleSummary(
        id=str(article.id),
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
        status=article.status.value,
        category_id=str(article.category_id),
        updated_at=article.updated_at,
    )


def _article_out(article: KbArticle) -> ArticleOut:
    return ArticleOut(
        id=str(article.id),
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
        status=article.status.value,
        category_id=str(article.category_id),
        updated_at=article.updated_at,
        doc=article.doc,
        published_at=article.published_at,
        author=(
            PublicAuthorOut(
                name=article.author.name, monogram=article.author.monogram
            )
            if article.author is not None
            else None
        ),
    )


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    scope: KbScope,
    scope_: Scope,
    session: DbSession,
) -> list[CategoryOut]:
    rows = await kb_categories.list_for(session, scope_.workspace_id, scope)
    return [_category_out(category, n) for category, n in rows]


@router.post(
    "/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED
)
async def create_category(
    payload: CategoryCreateRequest, scope_: Scope, session: DbSession
) -> CategoryOut:
    scope_.require_admin()
    category = await kb_categories.create(
        session,
        scope_.workspace_id,
        payload.name,
        _parsed_scope(payload.scope),
        parent_id=payload.parent_id,
        description=payload.description,
        icon=payload.icon,
    )
    await session.commit()
    return _category_out(category, 0)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryPatch,
    scope_: Scope,
    session: DbSession,
) -> CategoryOut:
    scope_.require_admin()
    category = await kb_categories.update(
        session,
        scope_.workspace_id,
        category_id,
        name=payload.name,
        position=payload.position,
        description=payload.description,
        icon=payload.icon,
    )
    await session.commit()
    rows = await kb_categories.list_for(session, scope_.workspace_id, category.scope)
    count = next((n for c, n in rows if c.id == category.id), 0)
    return _category_out(category, count)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID, scope_: Scope, session: DbSession
) -> Response:
    scope_.require_admin()
    await kb_categories.delete(session, scope_.workspace_id, category_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/articles", response_model=list[ArticleSummary])
async def list_articles(
    scope_: Scope,
    session: DbSession,
    scope: KbScope | None = None,
    status_filter: Annotated[ArticleStatus | None, Query(alias="status")] = None,
    q: str | None = None,
) -> list[ArticleSummary]:
    if q is not None:
        rows = await kb_articles.search(session, scope_.workspace_id, q, scope=scope)
    else:
        rows = await kb_articles.list_for(
            session, scope_.workspace_id, scope=scope, status=status_filter
        )
    return [_article_summary(article) for article in rows]


@router.post(
    "/articles", response_model=ArticleOut, status_code=status.HTTP_201_CREATED
)
async def create_article(
    payload: ArticleCreateRequest, scope_: Scope, session: DbSession
) -> ArticleOut:
    article = await kb_articles.create(
        session,
        scope_.workspace_id,
        payload.category_id,
        payload.title,
        scope_.user,
    )
    await session.commit()
    return _article_out(article)


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: uuid.UUID, scope_: Scope, session: DbSession
) -> ArticleOut:
    article = await kb_articles.get(session, scope_.workspace_id, article_id)
    return _article_out(article)


@router.patch("/articles/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: uuid.UUID,
    payload: ArticlePatch,
    scope_: Scope,
    session: DbSession,
) -> ArticleOut:
    article = await kb_articles.update(
        session,
        scope_.workspace_id,
        article_id,
        title=payload.title,
        excerpt=payload.excerpt,
        doc=payload.doc,
        category_id=payload.category_id,
    )
    await session.commit()
    return _article_out(article)


@router.post("/articles/{article_id}/status", response_model=ArticleOut)
async def set_article_status(
    article_id: uuid.UUID,
    payload: StatusRequest,
    scope_: Scope,
    session: DbSession,
) -> ArticleOut:
    article = await kb_articles.set_status(
        session, scope_.workspace_id, article_id, _parsed_status(payload.status)
    )
    await session.commit()
    return _article_out(article)


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: uuid.UUID, scope_: Scope, session: DbSession
) -> Response:
    await kb_articles.delete(session, scope_.workspace_id, article_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/articles/{article_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_image(
    article_id: uuid.UUID,
    scope_: Scope,
    session: DbSession,
    file: UploadFile,
) -> ImageOut:
    article = await kb_articles.get(session, scope_.workspace_id, article_id)

    # A cheap check on the declared size before pulling the body into
    # memory -- `file.size` is a client-supplied multipart header, so it is
    # a hint to save memory on the common case, not the guard: `store`'s
    # `len(content) > cap` check below remains the authoritative one.
    cap = get_settings().kb_image_max_bytes
    if file.size is not None and file.size > cap:
        raise Invalid(kb_images.oversize_message(cap))

    image = await kb_images.store(
        session,
        article,
        file.filename or "image",
        file.content_type or "",
        await file.read(),
    )
    await session.commit()
    return ImageOut(id=str(image.id), url=f"/api/kb/images/{image.id}")


@router.get("/images/{image_id}")
async def download_image(
    image_id: uuid.UUID, scope_: Scope, session: DbSession
) -> Response:
    row, content = await kb_images.read(session, scope_.workspace_id, image_id)
    headers = {"X-Content-Type-Options": "nosniff"}
    if row.content_type.lower() not in INLINE_SAFE_TYPES:
        headers["Content-Disposition"] = "attachment"
    return Response(
        content=content,
        media_type=safe_content_type(row.content_type),
        headers=headers,
    )
