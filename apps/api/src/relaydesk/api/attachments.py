import re
import uuid

from fastapi import APIRouter, Response

from relaydesk.api.deps import DbSession, Scope
from relaydesk.services import attachments

router = APIRouter()

# Defence in depth: the parser (email_parse.normalize._safe_filename)
# already strips control characters from a decoded filename before it ever
# reaches storage, but this is the one place that actually builds the
# header, so it strips again rather than trusting that upstream guarantee.
_HEADER_UNSAFE = re.compile(r'["\x00-\x1f\x7f]')


@router.get("/{attachment_id}")
async def download(
    attachment_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    row, content = await attachments.read(session, scope.workspace_id, attachment_id)
    filename = _HEADER_UNSAFE.sub("", row.filename)
    return Response(
        content=content,
        media_type=attachments.safe_content_type(row.content_type),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
