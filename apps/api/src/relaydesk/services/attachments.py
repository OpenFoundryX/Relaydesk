"""Files that arrived from strangers.

Content-addressed by SHA-256, never by the sender's filename: that string is
attacker-controlled, and the only safe thing to do with it is show it.
"""

import hashlib
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import NotFound
from relaydesk.models.attachment import Attachment
from relaydesk.models.message import Message

# Everything else is served as an opaque download. Note SVG is absent: it
# executes script when rendered inline.
INLINE_SAFE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)


def safe_content_type(content_type: str) -> str:
    return (
        content_type
        if content_type.lower() in INLINE_SAFE_TYPES
        else "application/octet-stream"
    )


def _root() -> Path:
    return Path(get_settings().attachment_dir)


async def store(
    session: AsyncSession, message: Message, parsed: Sequence[ParsedAttachment]
) -> list[Attachment]:
    cap = get_settings().attachment_max_bytes
    directory = _root() / str(message.workspace_id)
    directory.mkdir(parents=True, exist_ok=True)

    stored: list[Attachment] = []
    budget = cap
    for item in parsed:
        if len(item.content) > budget:
            # Skip and keep going: a single huge part must not cost the
            # message body or the parts after it.
            continue
        budget -= len(item.content)

        digest = hashlib.sha256(item.content).hexdigest()
        path = directory / digest
        if not path.exists():
            # Write to a temporary name and rename, so a crash mid-write
            # cannot leave a truncated file at a hash that claims to be whole.
            temporary = directory / f".{digest}.{uuid.uuid4().hex}"
            temporary.write_bytes(item.content)
            temporary.rename(path)

        row = Attachment(
            workspace_id=message.workspace_id,
            message_id=message.id,
            filename=item.filename,
            content_type=item.content_type,
            size_bytes=len(item.content),
            sha256=digest,
            storage_key=f"{message.workspace_id}/{digest}",
            inline=item.inline,
            content_id=item.content_id,
        )
        session.add(row)
        stored.append(row)

    await session.flush()
    return stored


async def read(
    session: AsyncSession, workspace_id: uuid.UUID, attachment_id: uuid.UUID
) -> tuple[Attachment, bytes]:
    row = await session.scalar(
        sa.select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.workspace_id == workspace_id,
        )
    )
    if row is None:
        raise NotFound("That attachment does not exist.")

    # Rebuilt from the validated workspace_id argument and the row's own
    # hash -- never from storage_key -- so a malformed storage_key (a bad
    # migration, a manual edit, a second writer) can't be trusted to stay
    # inside the workspace's directory just because it matched on the
    # workspace_id column. The descendant check is the same
    # structurally-impossible standard the write side already gets, carried
    # through to reads.
    base = (_root() / str(workspace_id)).resolve()
    path = (base / row.sha256).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise NotFound("That attachment does not exist.")
    return row, path.read_bytes()
