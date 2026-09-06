from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models import Workspace
from relaydesk.schemas.auth import WorkspaceOut
from relaydesk.schemas.workspace import SetupTaskOut, WorkspacePatch
from relaydesk.services import workspaces

router = APIRouter()


def _to_workspace_out(workspace: Workspace, seats: int) -> WorkspaceOut:
    return WorkspaceOut(
        id=str(workspace.id),
        name=workspace.name,
        slug=workspace.slug,
        monogram=workspace.monogram,
        plan=workspace.plan,
        trial_days_left=workspace.trial_days_left,
        seats=seats,
        tickets_this_period=workspace.tickets_this_period,
        projected_tickets=workspace.projected_tickets,
    )


@router.get("", response_model=WorkspaceOut)
async def get_workspace(scope: Scope, session: DbSession) -> WorkspaceOut:
    seats = await workspaces.active_seat_count(session, scope.workspace_id)
    return _to_workspace_out(scope.workspace, seats)


@router.patch("", response_model=WorkspaceOut)
async def patch_workspace(
    payload: WorkspacePatch, scope: Scope, session: DbSession
) -> WorkspaceOut:
    scope.require_admin()
    workspace = await workspaces.update_workspace(
        session, scope.workspace_id, payload.name, payload.timezone
    )
    seats = await workspaces.active_seat_count(session, scope.workspace_id)
    return _to_workspace_out(workspace, seats)


@router.get("/setup-tasks", response_model=list[SetupTaskOut])
async def get_setup_tasks(scope: Scope, session: DbSession) -> list[SetupTaskOut]:
    tasks = await workspaces.setup_tasks(session, scope.workspace_id)
    return [SetupTaskOut.model_validate(task) for task in tasks]
