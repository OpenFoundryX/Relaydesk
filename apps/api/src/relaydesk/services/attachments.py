"""Files that arrived from strangers.

Content-addressed by SHA-256, never by the sender's filename: that string is
attacker-controlled, and the only safe thing to do with it is show it.
"""

import logging
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
from relaydesk.services import blobs

logger = logging.getLogger(__name__)

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

    stored: list[Attachment] = []
    budget = cap
    for item in parsed:
        if len(item.content) > budget:
            # Skip and keep going: a single huge part must not cost the
            # message body or the parts after it. This is the right answer
            # for inbound mail, which has already been accepted by the time
            # it reaches here and cannot be refused after the fact -- but it
            # is a silent partial loss, so it is logged rather than dropped
            # on the floor.
            #
            # A caller that can still refuse the whole submission must not
            # rely on this: `tickets.validate` checks the same shared
            # `attachment_max_bytes` budget up front and rejects the
            # submission outright, so nothing reaching here from the portal
            # can ever be skipped.
            logger.warning(
                "attachment %r (%d bytes) skipped for message %s: "
                "%d of %d bytes of budget left",
                item.filename,
                len(item.content),
                message.id,
                budget,
                cap,
            )
            continue
        budget -= len(item.content)

        digest, storage_key = blobs.write(_root(), message.workspace_id, item.content)

        row = Attachment(
            workspace_id=message.workspace_id,
            message_id=message.id,
            filename=item.filename,
            content_type=item.content_type,
            size_bytes=len(item.content),
            sha256=digest,
            storage_key=storage_key,
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

    return row, blobs.read(_root(), workspace_id, row.sha256)
