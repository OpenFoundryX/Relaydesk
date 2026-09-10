"""Console management of widget embeds. Admin-gated, like every settings surface."""

import uuid

from fastapi import APIRouter, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.widget_key import WidgetKey
from relaydesk.schemas.widget_keys import (
    WidgetKeyCreate,
    WidgetKeyOut,
    WidgetKeyUpdate,
)
from relaydesk.services import widget_keys

router = APIRouter()


def _out(key: WidgetKey) -> WidgetKeyOut:
    return WidgetKeyOut(
        id=key.id,
        name=key.name,
        key=key.key,
        allowed_origins=key.allowed_origins,
        settings=key.settings,
        active=key.active,
        last_seen_at=key.last_seen_at,
        created_at=key.created_at,
    )


@router.get("", response_model=list[WidgetKeyOut])
async def list_route(scope: Scope, session: DbSession) -> list[WidgetKeyOut]:
    scope.require_admin()
    rows = await widget_keys.list_keys(session, scope.workspace.id)
    return [_out(row) for row in rows]


@router.post("", response_model=WidgetKeyOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: WidgetKeyCreate, scope: Scope, session: DbSession
) -> WidgetKeyOut:
    scope.require_admin()
    created = await widget_keys.create(
        session,
        scope.workspace.id,
        body.name,
        allowed_origins=body.allowed_origins,
        settings=body.settings,
        created_by_user_id=scope.user.id,
    )
    return _out(created)


@router.patch("/{key_id}", response_model=WidgetKeyOut)
async def update_route(
    key_id: uuid.UUID, body: WidgetKeyUpdate, scope: Scope, session: DbSession
) -> WidgetKeyOut:
    scope.require_admin()
    updated = await widget_keys.update(
        session,
        scope.workspace.id,
        key_id,
        name=body.name,
        allowed_origins=body.allowed_origins,
        settings=body.settings,
        active=body.active,
    )
    return _out(updated)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(key_id: uuid.UUID, scope: Scope, session: DbSession) -> None:
    scope.require_admin()
    await widget_keys.delete(session, scope.workspace.id, key_id)
