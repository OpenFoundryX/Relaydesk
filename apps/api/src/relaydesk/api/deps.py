from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import get_session
from relaydesk.errors import Forbidden, Unauthorized
from relaydesk.models import Membership, Role, User, Workspace
from relaydesk.services import auth

DbSession = Annotated[AsyncSession, Depends(get_session)]


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Authentication required.")
    return authorization[7:].strip()


async def current_user(
    session: DbSession, token: Annotated[str, Depends(bearer_token)]
) -> User:
    return await auth.resolve_session(session, token)


@dataclass(slots=True)
class WorkspaceScope:
    """Resolved tenant context. Every workspace-scoped route depends on this."""

    user: User
    membership: Membership
    workspace: Workspace

    @property
    def workspace_id(self):
        return self.workspace.id

    def require_admin(self) -> None:
        if self.membership.role is not Role.admin:
            raise Forbidden("This action requires an admin.")


async def workspace_scope(
    session: DbSession, user: Annotated[User, Depends(current_user)]
) -> WorkspaceScope:
    membership = await auth.active_membership(session, user)
    workspace = await session.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise Unauthorized("Workspace is unavailable.")
    return WorkspaceScope(user=user, membership=membership, workspace=workspace)


Scope = Annotated[WorkspaceScope, Depends(workspace_scope)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
