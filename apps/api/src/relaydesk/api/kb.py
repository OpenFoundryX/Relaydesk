import uuid

from fastapi import APIRouter, Response, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.errors import Invalid
from relaydesk.models.kb import KbCategory, KbScope
from relaydesk.schemas.kb import CategoryCreateRequest, CategoryOut, CategoryPatch
from relaydesk.services import kb_categories

router = APIRouter()


def _parsed_scope(raw: str) -> KbScope:
    try:
        return KbScope(raw)
    except ValueError:
        raise Invalid(f"Unknown scope {raw!r}.") from None


def _category_out(category: KbCategory, article_count: int) -> CategoryOut:
    return CategoryOut(
        id=str(category.id),
        name=category.name,
        slug=category.slug,
        scope=category.scope.value,
        position=category.position,
        article_count=article_count,
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
        session, scope_.workspace_id, payload.name, _parsed_scope(payload.scope)
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
