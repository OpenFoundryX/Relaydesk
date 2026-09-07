import uuid

from fastapi import APIRouter, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models import ApiKey
from relaydesk.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from relaydesk.services import api_keys

router = APIRouter()


def _out(key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(key.id),
        name=key.name,
        prefix=key.prefix,
        scopes=list(key.scopes),
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_route(scope: Scope, session: DbSession) -> list[ApiKeyOut]:
    scope.require_admin()
    rows = await api_keys.list_keys(session, scope.workspace_id)
    return [_out(row) for row in rows]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: ApiKeyCreate, scope: Scope, session: DbSession
) -> ApiKeyCreated:
    """Mint a key and return its secret, once.

    Admin only: a key is a credential for the whole workspace, and handing
    an agent the ability to mint one with ``messages:write`` would be
    handing them a way to mail customers from outside the console with no
    session to revoke.
    """
    scope.require_admin()
    token, key = await api_keys.mint(
        session,
        scope.workspace_id,
        name=payload.name,
        scopes=payload.scopes,
        created_by_user_id=scope.user.id,
    )
    return ApiKeyCreated(token=token, key=_out(key))


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_route(key_id: uuid.UUID, scope: Scope, session: DbSession) -> None:
    scope.require_admin()
    await api_keys.revoke(session, scope.workspace_id, key_id)
