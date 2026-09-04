import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from relaydesk.api.deps import DbSession, Scope, client_ip
from relaydesk.models import Role, Workspace
from relaydesk.schemas.auth import TokenResponse
from relaydesk.schemas.team import (
    AcceptRequest,
    InvitePreview,
    InviteRequest,
    MemberPatch,
    RoleLabel,
    TeamMemberOut,
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
@invites_router.get("/{token}", response_model=InvitePreview)
async def preview_invite(token: str, session: DbSession) -> InvitePreview:
    invite = await team.read_invite(session, token)
    workspace = await session.get(Workspace, invite.workspace_id)
    return InvitePreview(
        workspace_name=workspace.name,
        email=invite.email,
        role=team.ROLE_LABEL[invite.role],
    )


@invites_router.post("/{token}/accept", response_model=TokenResponse)
async def accept_invite_route(
    token: str,
    payload: AcceptRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    user = await team.accept_invite(session, token, payload.name, payload.password)
    membership = await auth.default_membership(session, user)
    session_token, row = await auth.create_session(
        session, user, membership, user_agent=user_agent, ip=ip
    )
    return TokenResponse(token=session_token, expires_at=row.expires_at)
