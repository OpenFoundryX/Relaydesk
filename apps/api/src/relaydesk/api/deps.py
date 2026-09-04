import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import get_session
from relaydesk.errors import Forbidden, Unauthorized
from relaydesk.models import Membership, Role, Session, User, Workspace
from relaydesk.services import auth

DbSession = Annotated[AsyncSession, Depends(get_session)]


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Authentication required.")
    token = authorization[7:].strip()
    if not token:
        raise Unauthorized("Authentication required.")
    return token


async def current_session(
    session: DbSession, token: Annotated[str, Depends(bearer_token)]
) -> tuple[User, Session]:
    return await auth.resolve_session(session, token)


async def current_user(
    resolved: Annotated[tuple[User, Session], Depends(current_session)],
) -> User:
    return resolved[0]


@dataclass(slots=True)
class WorkspaceScope:
    """Resolved tenant context. Every workspace-scoped route depends on this."""

    user: User
    membership: Membership
    workspace: Workspace

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    def require_admin(self) -> None:
        if self.membership.role is not Role.admin:
            raise Forbidden("This action requires an admin.")


async def workspace_scope(
    session: DbSession,
    resolved: Annotated[tuple[User, Session], Depends(current_session)],
) -> WorkspaceScope:
    user, row = resolved
    membership = await auth.active_membership(session, user, row.workspace_id)
    workspace = await session.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise Unauthorized("Workspace is unavailable.")
    return WorkspaceScope(user=user, membership=membership, workspace=workspace)


Scope = Annotated[WorkspaceScope, Depends(workspace_scope)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
