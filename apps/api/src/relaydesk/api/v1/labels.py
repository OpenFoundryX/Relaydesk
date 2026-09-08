from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

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


@router.post(
    "",
    response_model=LabelOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": LabelOut,
            "description": "The label already existed and was returned unchanged.",
        }
    },
)
async def create_route(
    payload: LabelCreate,
    principal: Writer,
    session: DbSession,
    response: Response,
) -> LabelOut:
    """Create a label.

    Idempotent by name -- ``labels.name`` is CITEXT, so "Refunds" and
    "refunds" are the same label and a repeat returns the existing one.

    Answers 201 for a new label and 200 when the name already existed,
    exactly as ``POST /v1/conversations`` does for a matched ``external_id``.
    Both creates on this surface are idempotent, so both have to report the
    outcome the same way: an importer creating labels and conversations in
    one pass and counting creations by status code would otherwise log
    "created 40 labels" on every re-run, with no way to learn that 39 of
    them already existed.
    """
    label, created = await labels.create_label(
        session, principal.workspace_id, payload.name
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return label_out(label)
