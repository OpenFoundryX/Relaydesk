from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status

from relaydesk.api.deps import DbSession, Scope, bearer_token, client_ip
from relaydesk.schemas.auth import (
    GoogleExchangeRequest,
    GoogleUrlResponse,
    LoginRequest,
    MembershipOut,
    MePatch,
    MeResponse,
    TokenResponse,
    UserOut,
    WorkspaceOut,
)
from relaydesk.security.oauth_google import authorization_url, exchange_code
from relaydesk.security.tokens import generate_token
from relaydesk.services import auth, workspaces
from relaydesk.services.team import monogram_for

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    user = await auth.authenticate(session, payload.email, payload.password)
    membership = await auth.default_membership(session, user)
    token, row = await auth.create_session(
        session, user, membership, user_agent=user_agent, ip=ip
    )
    return TokenResponse(token=token, expires_at=row.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: DbSession, token: Annotated[str, Depends(bearer_token)]
) -> Response:
    await auth.revoke_session(session, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/google/url", response_model=GoogleUrlResponse)
async def google_url(
    redirect_uri: Annotated[str, Query(alias="redirectUri")],
) -> GoogleUrlResponse:
    # The rest of the API's JSON is camelCase via alias_generator=to_camel,
    # but that only covers pydantic model fields, not a plain query
    # parameter — so this one needs an explicit alias to match what the web
    # action sends (`?redirectUri=`).
    state = generate_token()
    return GoogleUrlResponse(url=authorization_url(redirect_uri, state), state=state)


@router.post("/google/exchange", response_model=TokenResponse)
async def google_exchange(
    payload: GoogleExchangeRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    profile = await exchange_code(payload.code, payload.redirect_uri)
    user, membership = await auth.login_with_google(session, profile)
    token, row = await auth.create_session(
        session, user, membership, user_agent=user_agent, ip=ip
    )
    return TokenResponse(token=token, expires_at=row.expires_at)


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
            notify_on_assignment=scope.user.notify_on_assignment,
        ),
        workspace=WorkspaceOut(
            id=str(scope.workspace.id),
            name=scope.workspace.name,
            slug=scope.workspace.slug,
            monogram=scope.workspace.monogram,
            plan=scope.workspace.plan,
            trial_days_left=scope.workspace.trial_days_left,
            seats=seats,
            tickets_this_period=scope.workspace.tickets_this_period,
            projected_tickets=scope.workspace.projected_tickets,
        ),
        membership=MembershipOut(role=scope.membership.role.value),
    )


@router.patch("/me", response_model=MeResponse)
async def update_me(payload: MePatch, scope: Scope, session: DbSession) -> MeResponse:
    if payload.name is not None:
        scope.user.name = payload.name.strip()
        # Otherwise a rename leaves the monogram showing the old initials --
        # team.accept_invite and team.py's other name-setting paths already
        # derive it the same way.
        scope.user.monogram = monogram_for(scope.user.name)
    if payload.notify_on_assignment is not None:
        scope.user.notify_on_assignment = payload.notify_on_assignment
    await session.commit()
    return await me(scope, session)
