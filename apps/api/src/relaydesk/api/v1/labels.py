from typing import Annotated

from fastapi import APIRouter, Depends, status

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope
from relaydesk.schemas.v1 import LabelCreate, LabelOut, label_out
from relaydesk.services import labels

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.labels_read))]
Writer = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.labels_write))]


@router.get("", response_model=list[LabelOut])
async def list_route(principal: Reader, session: DbSession) -> list[LabelOut]:
    rows = await labels.list_labels(session, principal.workspace_id)
    return [label_out(row) for row in rows]


@router.post("", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: LabelCreate, principal: Writer, session: DbSession
) -> LabelOut:
    """Idempotent by name -- ``labels.name`` is CITEXT, so "Refunds" and
    "refunds" are the same label and a repeat returns the existing one."""
    label = await labels.create_label(session, principal.workspace_id, payload.name)
    return label_out(label)
