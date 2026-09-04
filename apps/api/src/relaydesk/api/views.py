from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.schemas.base import CamelModel
from relaydesk.services import views

router = APIRouter()


class SavedViewOut(CamelModel):
    id: str
    name: str
    count: int


@router.get("", response_model=list[SavedViewOut])
async def list_saved_views(scope: Scope, session: DbSession) -> list[SavedViewOut]:
    rows = await views.list_views(session, scope.workspace_id)
    return [
        SavedViewOut(
            id=str(view.id),
            name=view.name,
            count=await views.count_for_view(
                session, scope.workspace_id, view, scope.user
            ),
        )
        for view in rows
    ]
