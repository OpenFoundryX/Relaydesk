"""Raising a widget session's flags, once each, whatever the visitor does."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.widget_key import WidgetKey
from relaydesk.models.widget_session import WidgetSession

# The visitor supplies this, so it is matched against a closed set rather
# than written through to a column name.
_FLAGS = {"searched": "searched", "read": "read_article", "submitted": "submitted"}


async def record(
    session: AsyncSession,
    widget_key: WidgetKey,
    session_id: uuid.UUID,
    kind: str,
) -> None:
    """Raise one flag on a session, creating the row the first time.

    An upsert rather than a read-then-write: the frame fires these
    concurrently -- a search and an article open can overlap -- and two
    inserts racing on the same id would otherwise be a primary-key error on
    an endpoint whose failure the visitor must never see.

    Flags only ever go up. ``ON CONFLICT`` re-asserts the raised one and
    leaves the rest alone, so events arriving out of order still land.
    """
    flag = _FLAGS.get(kind)
    if flag is None:
        raise Invalid("Unknown widget event.")

    now = datetime.now(UTC)
    statement = insert(WidgetSession).values(
        id=session_id,
        workspace_id=widget_key.workspace_id,
        widget_key_id=widget_key.id,
        started_at=now,
        created_at=now,
        updated_at=now,
        **{flag: True},
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[WidgetSession.id],
            set_={flag: True, "updated_at": now},
        )
    )
    await session.flush()
