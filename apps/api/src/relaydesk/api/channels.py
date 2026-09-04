import uuid

from fastapi import APIRouter, Response, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.channel_account import ChannelAccount
from relaydesk.schemas.channel import ChannelCreateRequest, ChannelOut
from relaydesk.services import channel_accounts

router = APIRouter()


def _out(account: ChannelAccount, slug: str) -> ChannelOut:
    return ChannelOut(
        id=str(account.id),
        address=channel_accounts.address_for(account, slug),
        display_name=account.display_name,
        active=account.active,
    )


@router.get("/email", response_model=list[ChannelOut])
async def list_route(scope: Scope, session: DbSession) -> list[ChannelOut]:
    accounts = await channel_accounts.list_for(session, scope.workspace_id)
    return [_out(account, scope.workspace.slug) for account in accounts]


@router.post("/email", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: ChannelCreateRequest, scope: Scope, session: DbSession
) -> ChannelOut:
    scope.require_admin()
    account = await channel_accounts.create(
        session, scope.workspace_id, payload.display_name
    )
    await session.commit()
    return _out(account, scope.workspace.slug)


@router.delete("/email/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    channel_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    await channel_accounts.deactivate(session, scope.workspace_id, channel_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
