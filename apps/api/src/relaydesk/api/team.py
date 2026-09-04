import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from relaydesk.api.deps import DbSession, Scope, client_ip
from relaydesk.errors import NotFound
from relaydesk.models import Role, Workspace
from relaydesk.schemas.auth import TokenResponse
from relaydesk.schemas.team import (
    AcceptRequest,
    InvitePreview,
    InviteRequest,
    MemberPatch,
    RoleLabel,
    TeamMemberOut,
    TokenRequest,
)
from relaydesk.services import auth, notifications, team

router = APIRouter()
invites_router = APIRouter()


def _role_from_label(label: RoleLabel) -> Role:
    return Role.admin if label == "Admin" else Role.agent


@router.get("", response_model=list[TeamMemberOut])
async def list_team(scope: Scope, session: DbSession) -> list[TeamMemberOut]:
    members = await team.list_members(session, scope.workspace_id)
    return [TeamMemberOut.model_validate(member) for member in members]


# Invites are enabled because the token is delivered to the invited address
# and returned to nobody. Possession of it is therefore proof of control of
# that address, which is the property slice 1 required before re-enabling.
# Do not add an invite URL to any response body: that hands the token back to
# the caller and reinstates the takeover this replaced.
@router.post("/invites", status_code=status.HTTP_202_ACCEPTED)
async def create_team_invite(
    payload: InviteRequest, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    _invite, token = await team.create_invite(
        session,
        scope.workspace_id,
        payload.email,
        _role_from_label(payload.role),
        scope.user.id,
    )
    await session.commit()
    notifications.notify_invite(
        payload.email, token, scope.workspace.name, scope.user.name
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_invite(
    invite_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    await team.revoke_invite(session, scope.workspace_id, invite_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_team_member(
    membership_id: uuid.UUID,
    payload: MemberPatch,
    scope: Scope,
    session: DbSession,
) -> Response:
    scope.require_admin()
    await team.update_member_role(
        session, scope.workspace_id, membership_id, _role_from_label(payload.role)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_member(
    membership_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    await team.remove_member(session, scope.workspace_id, membership_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Public: acceptance is gated on possession of a token that was mailed to
# the invited address, not on a session — the accepter has none yet.
#
# The token travels in the request BODY on both routes, never in the URL.
# A path segment (the original `GET /invites/{token}`) is written verbatim
# to the access log on every request — uvicorn's access log is on by
# default and there is no config here that disables it — so a preview alone
# would put a still-usable token in plaintext in every log sink between here
# and stdout. That is the same takeover this task closes, relocated from the
# response body to the log. A query string has the identical problem. Do
# not put the token back in a path or query parameter for either route.
@invites_router.post("/preview", response_model=InvitePreview)
async def preview_invite(payload: TokenRequest, session: DbSession) -> InvitePreview:
    invite = await team.read_invite(session, payload.token)
    workspace = await session.get(Workspace, invite.workspace_id)
    if workspace is None:
        # The workspace was deleted out from under a still-live invite (the
        # FK is ON DELETE CASCADE, so this shouldn't happen in practice —
        # defensive anyway). Surfacing that as anything but "this invite is
        # not valid" would leak workspace lifecycle information to an
        # unauthenticated caller; left unguarded it also crashes on
        # `workspace.name` below with an unhandled AttributeError -> 500.
        raise NotFound("This invite is not valid.")
    return InvitePreview(
        workspace_name=workspace.name,
        email=invite.email,
        role=team.ROLE_LABEL[invite.role],
    )


@invites_router.post("/accept", response_model=TokenResponse)
async def accept_invite_route(
    payload: AcceptRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    user, membership = await team.accept_invite(
        session, payload.token, payload.name, payload.password
    )
    session_token, row = await auth.create_session(
        session, user, membership, user_agent=user_agent, ip=ip
    )
    return TokenResponse(token=session_token, expires_at=row.expires_at)
