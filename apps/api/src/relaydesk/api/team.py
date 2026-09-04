import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from relaydesk.api.deps import DbSession, Scope, client_ip
from relaydesk.config import get_settings
from relaydesk.errors import NotFound
from relaydesk.models import Role, Workspace
from relaydesk.schemas.auth import TokenResponse
from relaydesk.schemas.team import (
    AcceptInviteRequest,
    InviteCreated,
    InvitePreview,
    InviteRequest,
    MemberPatch,
    RoleLabel,
    TeamMemberOut,
)
from relaydesk.services import auth, team

router = APIRouter()
invite_router = APIRouter()


def _role_from_label(label: RoleLabel) -> Role:
    return Role.admin if label == "Admin" else Role.agent


@router.get("", response_model=list[TeamMemberOut])
async def list_team(scope: Scope, session: DbSession) -> list[TeamMemberOut]:
    members = await team.list_members(session, scope.workspace_id)
    return [TeamMemberOut.model_validate(member) for member in members]


@router.post(
    "/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED
)
async def create_team_invite(
    payload: InviteRequest, scope: Scope, session: DbSession
) -> InviteCreated:
    scope.require_admin()
    invite, token = await team.create_invite(
        session,
        scope.workspace_id,
        payload.email,
        _role_from_label(payload.role),
        scope.user.id,
    )
    settings = get_settings()
    return InviteCreated(
        id=str(invite.id), invite_url=f"{settings.web_url}/invite/{token}"
    )


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_invite(
    invite_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    await team.revoke_invite(session, scope.workspace_id, invite_id)
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


@invite_router.get("/{token}", response_model=InvitePreview)
async def preview_invite(token: str, session: DbSession) -> InvitePreview:
    invite = await team.read_invite(session, token)
    workspace = await session.get(Workspace, invite.workspace_id)
    if workspace is None:
        raise NotFound("This invite is not valid.")
    return InvitePreview(
        workspace_name=workspace.name,
        email=invite.email,
        role=team.ROLE_LABEL[invite.role],
    )


@invite_router.post("/{token}/accept", response_model=TokenResponse)
async def accept_invite(
    token: str,
    payload: AcceptInviteRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    """Accepting an invite signs you in, so the console can go straight to
    the inbox. Same response shape as POST /auth/login."""
    user = await team.accept_invite(session, token, payload.name, payload.password)
    token_value, row = await auth.create_session(
        session, user, user_agent=user_agent, ip=ip
    )
    return TokenResponse(token=token_value, expires_at=row.expires_at)
