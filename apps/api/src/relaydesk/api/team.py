import uuid

from fastapi import APIRouter, Response, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.errors import Unavailable
from relaydesk.models import Role
from relaydesk.schemas.team import (
    InviteRequest,
    MemberPatch,
    RoleLabel,
    TeamMemberOut,
)
from relaydesk.services import team

router = APIRouter()

INVITES_UNAVAILABLE_MESSAGE = (
    "Invites require email delivery, which is not available yet."
)


def _role_from_label(label: RoleLabel) -> Role:
    return Role.admin if label == "Admin" else Role.agent


@router.get("", response_model=list[TeamMemberOut])
async def list_team(scope: Scope, session: DbSession) -> list[TeamMemberOut]:
    members = await team.list_members(session, scope.workspace_id)
    return [TeamMemberOut.model_validate(member) for member in members]


# --- Invites: disabled, not just unmounted -------------------------------
#
# Three successive security reviews each found a live cross-tenant account
# takeover here, and each fix closed one path and opened another. The root
# cause is architectural: an invite binds an email address that nobody has
# proved they control, and accepting one both adopts a (possibly
# pre-existing) account and issues a 30-day session. There is no mailer and
# no password-reset flow in this slice, so there is no way to close that
# loop here — see `relaydesk.services.team` for the full residual-risk list.
#
# These two routes are kept mounted (rather than removed) only so the
# console gets a clear, stable 503 instead of a 404 that looks like a
# routing bug. The public accept/preview routes (`GET/POST /invites/...`)
# are not mounted at all — see relaydesk.api.router.
#
# Do not gate this behind a config flag or environment variable: a flag
# that defaults off still ships the vulnerability behind a switch that
# someone will eventually flip without reading this comment. Re-enabling
# requires a code change, made only once acceptance proves control of the
# address (e.g. a confirmation link sent to the invited email).
@router.post("/invites", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
async def create_team_invite(payload: InviteRequest, scope: Scope) -> None:
    scope.require_admin()
    raise Unavailable(INVITES_UNAVAILABLE_MESSAGE)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
async def delete_team_invite(invite_id: uuid.UUID, scope: Scope) -> None:
    scope.require_admin()
    raise Unavailable(INVITES_UNAVAILABLE_MESSAGE)


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
