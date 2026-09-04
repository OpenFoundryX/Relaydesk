import uuid

from fastapi import APIRouter, Response

from relaydesk.api.deps import DbSession, Scope
from relaydesk.services import attachments

router = APIRouter()


@router.get("/{attachment_id}")
async def download(
    attachment_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    row, content = await attachments.read(session, scope.workspace_id, attachment_id)
    filename = row.filename.replace('"', "")
    return Response(
        content=content,
        media_type=attachments.safe_content_type(row.content_type),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
