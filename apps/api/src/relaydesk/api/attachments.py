import re
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Response

from relaydesk.api.deps import DbSession, Scope
from relaydesk.services import attachments

router = APIRouter()

# Defence in depth: the parser (email_parse.normalize._safe_filename)
# already strips control characters from a decoded filename before it ever
# reaches storage, but this is the one place that actually builds the
# header, so it strips again rather than trusting that upstream guarantee.
_HEADER_UNSAFE = re.compile(r'["\x00-\x1f\x7f]')
# A backslash is unsafe inside the quoted-string `filename="..."` fallback
# specifically (RFC 6266/2616 escaping), not because it could inject a
# header -- _HEADER_UNSAFE already rules that out.
_QUOTED_STRING_UNSAFE = re.compile(r'["\\]')


def _content_disposition(filename: str) -> str:
    """Starlette encodes response headers as latin-1, so any attachment
    named in CJK, Cyrillic, Greek, or carrying an emoji -- ordinary
    international support mail, not an edge case -- would otherwise 500 the
    download. RFC 5987/6266's ``filename*`` gives every client the exact
    UTF-8 name; the plain ``filename=`` stays as an ASCII-safe fallback for
    a client that only understands that form.
    """
    safe = _HEADER_UNSAFE.sub("", filename)
    fallback = _QUOTED_STRING_UNSAFE.sub("", safe.encode("ascii", "ignore").decode())
    fallback = fallback.strip() or "attachment"
    encoded = quote(safe.encode("utf-8"), safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


@router.get("/{attachment_id}")
async def download(
    attachment_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    row, content = await attachments.read(session, scope.workspace_id, attachment_id)
    return Response(
        content=content,
        media_type=attachments.safe_content_type(row.content_type),
        headers={
            "Content-Disposition": _content_disposition(row.filename),
            "X-Content-Type-Options": "nosniff",
        },
    )
