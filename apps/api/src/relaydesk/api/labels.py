from fastapi import APIRouter, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.schemas.conversation import LabelCreateRequest, LabelOut
from relaydesk.services import labels

router = APIRouter()


@router.get("", response_model=list[LabelOut])
async def list_route(scope: Scope, session: DbSession) -> list[LabelOut]:
    rows = await labels.list_labels(session, scope.workspace_id)
    return [
        LabelOut(id=str(label.id), name=label.name, color=label.color.value)
        for label in rows
    ]


@router.post("", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: LabelCreateRequest, scope: Scope, session: DbSession
) -> LabelOut:
    label = await labels.create_label(session, scope.workspace_id, payload.name)
    return LabelOut(id=str(label.id), name=label.name, color=label.color.value)
