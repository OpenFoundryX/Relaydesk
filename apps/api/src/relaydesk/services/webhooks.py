"""The webhook registry: everything that touches the table, nothing that
touches the network.

The counterpart to ``services.webhook_dispatch``, which takes a row and calls
it. Keeping the two apart is what lets the dispatcher be tested without a
database and this module without a socket.
"""

import re
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.models import Webhook, WebhookMethod
from relaydesk.security.tokens import generate_token
from relaydesk.services.url_guard import ensure_https_url

# A tool name, not a title: lowercase, starting with a letter, and otherwise
# letters, digits and underscores. It is what a caller writes to select this
# webhook, so it has to survive being written by hand.
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Long enough that the prefix costs nothing: 6 characters of label plus 43 of
# CSPRNG output, and the column is sized for it.
SECRET_PREFIX = "whsec_"


def _new_secret() -> str:
    return f"{SECRET_PREFIX}{generate_token()}"


def _validate_name(name: str) -> str:
    trimmed = name.strip()
    if not NAME_PATTERN.match(trimmed):
        raise Invalid(
            "A webhook name must start with a letter and use only lowercase "
            "letters, digits and underscores -- refund_order, not "
            '"Refund Order".'
        )
    return trimmed


def _validate_description(description: str) -> str:
    trimmed = description.strip()
    if not trimmed:
        # Not a formality: this is the text a tool-selecting caller reads to
        # decide whether this is the right endpoint.
        raise Invalid("A webhook needs a description of what it does.")
    return trimmed[:500]


async def create(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    name: str,
    description: str,
    method: WebhookMethod | str,
    url: str,
    params: Sequence[dict],
    created_by_user_id: uuid.UUID | None,
) -> Webhook:
    """Register a webhook, with a secret it is the only maker of."""
    # Shape only. Whether the URL is reachable is decided at dispatch, because
    # DNS moves between here and there (spec D8).
    ensure_https_url(url)

    webhook = Webhook(
        workspace_id=workspace_id,
        name=_validate_name(name),
        description=_validate_description(description),
        method=WebhookMethod(method),
        url=url,
        params=list(params),
        secret=_new_secret(),
        created_by_user_id=created_by_user_id,
    )
    session.add(webhook)
    try:
        await session.commit()
    except IntegrityError:
        # The unique index is the authority rather than a prior SELECT, which
        # two concurrent creates would both pass.
        await session.rollback()
        raise Conflict(f"A webhook named {name} already exists.") from None
    return webhook


async def list_webhooks(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[Webhook]:
    """The workspace's webhooks, newest first."""
    return list(
        await session.scalars(
            sa.select(Webhook)
            .where(Webhook.workspace_id == workspace_id)
            .order_by(Webhook.created_at.desc(), Webhook.id.desc())
        )
    )


async def get(
    session: AsyncSession, workspace_id: uuid.UUID, webhook_id: uuid.UUID
) -> Webhook:
    """One webhook, or ``NotFound``.

    Scoped by workspace, and a webhook belonging to another workspace raises
    ``NotFound`` rather than ``Forbidden`` -- the slice-1 isolation contract,
    under which a foreign id must be indistinguishable from one that does not
    exist.
    """
    webhook = await session.scalar(
        sa.select(Webhook).where(
            Webhook.id == webhook_id, Webhook.workspace_id == workspace_id
        )
    )
    if webhook is None:
        raise NotFound("Webhook not found.")
    return webhook


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    webhook_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    method: WebhookMethod | str | None = None,
    url: str | None = None,
    params: Sequence[dict] | None = None,
) -> Webhook:
    """Change what was supplied and leave the rest alone.

    ``None`` means "not supplied" for every field, which is why clearing the
    parameter list is an empty list rather than a null.
    """
    webhook = await get(session, workspace_id, webhook_id)

    if name is not None:
        webhook.name = _validate_name(name)
    if description is not None:
        webhook.description = _validate_description(description)
    if method is not None:
        webhook.method = WebhookMethod(method)
    if url is not None:
        ensure_https_url(url)
        webhook.url = url
    if params is not None:
        # Reassigned rather than mutated: a JSONB column tracks replacement,
        # not in-place edits to the list it holds.
        webhook.params = list(params)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise Conflict(f"A webhook named {name} already exists.") from None
    return webhook


async def rotate_secret(
    session: AsyncSession, workspace_id: uuid.UUID, webhook_id: uuid.UUID
) -> Webhook:
    """Replace the signing secret, invalidating every signature made with the
    old one from this moment on.

    A first-class operation rather than delete-and-recreate, because the
    endpoint, its description and its parameters are what a caller has been
    written against; only the key needs to change when it leaks.
    """
    webhook = await get(session, workspace_id, webhook_id)
    webhook.secret = _new_secret()
    await session.commit()
    return webhook


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, webhook_id: uuid.UUID
) -> None:
    """A real delete. Nothing references a webhook, so unlike ``ApiKey`` there
    is no attribution to keep alive with a tombstone."""
    webhook = await get(session, workspace_id, webhook_id)
    await session.delete(webhook)
    await session.commit()
