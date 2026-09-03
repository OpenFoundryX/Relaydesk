from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from relaydesk.api.deps import DbSession, Scope, bearer_token, client_ip
from relaydesk.schemas.auth import (
    LoginRequest,
    MembershipOut,
    MeResponse,
    TokenResponse,
    UserOut,
    WorkspaceOut,
)
from relaydesk.services import auth, workspaces

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    user = await auth.authenticate(session, payload.email, payload.password)
    await auth.active_membership(session, user)
    token, row = await auth.create_session(session, user, user_agent=user_agent, ip=ip)
    return TokenResponse(token=token, expires_at=row.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: DbSession, token: Annotated[str, Depends(bearer_token)]
) -> Response:
    await auth.revoke_session(session, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(scope: Scope, session: DbSession) -> MeResponse:
    seats = await workspaces.active_seat_count(session, scope.workspace_id)
    return MeResponse(
        user=UserOut(
            id=str(scope.user.id),
            name=scope.user.name,
            email=scope.user.email,
            monogram=scope.user.monogram,
            time_zone=scope.user.timezone,
        ),
        workspace=WorkspaceOut(
            id=str(scope.workspace.id),
            name=scope.workspace.name,
            monogram=scope.workspace.monogram,
            plan=scope.workspace.plan,
            trial_days_left=scope.workspace.trial_days_left,
            seats=seats,
            tickets_this_period=scope.workspace.tickets_this_period,
            projected_tickets=scope.workspace.projected_tickets,
        ),
        membership=MembershipOut(role=scope.membership.role.value),
    )
