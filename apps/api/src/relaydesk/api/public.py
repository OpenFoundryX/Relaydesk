"""Anonymous, read-only routes for the customer-facing portal.

Everything here is reachable without a session by design -- a published
knowledge base is public. That makes the rule for this module simple and
absolute: return display information and published content, never anything
about tickets, members, plans, or usage.
"""

import sqlalchemy as sa
from fastapi import APIRouter

from relaydesk.api.deps import DbSession
from relaydesk.errors import NotFound
from relaydesk.models.workspace import Workspace
from relaydesk.schemas.kb import PublicWorkspaceOut
from relaydesk.services.workspaces import RESERVED_SLUGS

router = APIRouter()


async def resolve_workspace(session: DbSession, slug: str) -> Workspace:
    """Shared by every public route. A reserved label is a 404, not a lookup."""
    if slug.lower() in RESERVED_SLUGS:
        raise NotFound("No such workspace.")
    workspace = await session.scalar(
        sa.select(Workspace).where(Workspace.slug == slug.lower())
    )
    if workspace is None:
        raise NotFound("No such workspace.")
    return workspace


@router.get("/workspaces/{slug}", response_model=PublicWorkspaceOut)
async def read_workspace(slug: str, session: DbSession) -> PublicWorkspaceOut:
    workspace = await resolve_workspace(session, slug)
    return PublicWorkspaceOut(name=workspace.name, monogram=workspace.monogram)
