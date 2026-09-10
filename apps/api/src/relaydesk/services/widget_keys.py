"""Minting and resolving the credential a widget embed carries."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models.widget_key import WidgetKey
from relaydesk.services import widget_origins

# Long enough that guessing is pointless, short enough to paste. The value is
# public, so this is about enumeration, not secrecy.
_KEY_BYTES = 16
_TOUCH_EVERY = timedelta(minutes=1)


def _new_key() -> str:
    return "rdw_" + secrets.token_hex(_KEY_BYTES)


def _clean_origins(raw: list[str] | None) -> list[str]:
    """Normalise, de-duplicate, and refuse anything that is not an origin.

    Order is preserved so the console shows origins as the admin entered
    them rather than re-sorted underneath.
    """
    cleaned: list[str] = []
    for entry in raw or []:
        normalised = widget_origins.normalise(entry)
        if normalised is None:
            raise Invalid(f"{entry!r} is not a valid site address.")
        if normalised not in cleaned:
            cleaned.append(normalised)
    return cleaned


async def create(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    *,
    allowed_origins: list[str] | None = None,
    settings: dict | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> WidgetKey:
    label = name.strip()
    if not label:
        raise Invalid("Give this embed a name.")

    key = WidgetKey(
        workspace_id=workspace_id,
        name=label,
        key=_new_key(),
        allowed_origins=_clean_origins(allowed_origins),
        settings=settings or {},
        created_by_user_id=created_by_user_id,
    )
    session.add(key)
    await session.flush()
    return key


async def list_keys(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[WidgetKey]:
    result = await session.scalars(
        sa.select(WidgetKey)
        .where(WidgetKey.workspace_id == workspace_id)
        .order_by(WidgetKey.created_at.desc())
    )
    return list(result)


async def get(
    session: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID
) -> WidgetKey:
    key = await session.scalar(
        sa.select(WidgetKey).where(
            WidgetKey.id == key_id, WidgetKey.workspace_id == workspace_id
        )
    )
    if key is None:
        raise NotFound("No such embed.")
    return key


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    key_id: uuid.UUID,
    *,
    name: str | None = None,
    allowed_origins: list[str] | None = None,
    settings: dict | None = None,
    active: bool | None = None,
) -> WidgetKey:
    key = await get(session, workspace_id, key_id)
    if name is not None:
        label = name.strip()
        if not label:
            raise Invalid("Give this embed a name.")
        key.name = label
    if allowed_origins is not None:
        key.allowed_origins = _clean_origins(allowed_origins)
    if settings is not None:
        key.settings = settings
    if active is not None:
        key.active = active
    await session.flush()
    return key


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID
) -> None:
    """Deleting the row *is* the revocation; there is no ``revoked_at``."""
    key = await get(session, workspace_id, key_id)
    await session.delete(key)
    await session.flush()


async def resolve(session: AsyncSession, key: str) -> WidgetKey:
    """The key's workspace, or ``NotFound``.

    Unknown, inactive and deleted keys all raise the same exception with the
    same message. Telling them apart would let a caller walk the key space
    and learn which embeds exist.
    """
    found = await session.scalar(
        sa.select(WidgetKey).where(WidgetKey.key == key, WidgetKey.active.is_(True))
    )
    if found is None:
        raise NotFound("No such embed.")
    return found


async def touch(session: AsyncSession, widget_key: WidgetKey) -> None:
    """Record that the embed is still installed, at most once a minute.

    Without the interval this is a write on every page view of every site
    that embeds the widget, to answer a question nobody asks more than once
    a day.
    """
    now = datetime.now(UTC)
    seen = widget_key.last_seen_at
    if seen is not None and now - seen < _TOUCH_EVERY:
        return
    widget_key.last_seen_at = now
    await session.flush()
