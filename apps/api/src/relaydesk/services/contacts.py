import uuid

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models.contact import Contact
from relaydesk.services import pagination


async def _find(
    session: AsyncSession, workspace_id: uuid.UUID, email: str
) -> Contact | None:
    return await session.scalar(
        sa.select(Contact).where(
            Contact.workspace_id == workspace_id, Contact.email == email
        )
    )


async def upsert(
    session: AsyncSession, workspace_id: uuid.UUID, email: str, name: str
) -> Contact:
    """Find or create a contact. ``contacts.email`` is CITEXT, so lookup is
    already case-insensitive."""
    contact = await _find(session, workspace_id, email)
    if contact is not None:
        # A later message may carry a better display name than the first did.
        if name and contact.name != name and "@" in contact.name:
            contact.name = name
        return contact

    contact = Contact(workspace_id=workspace_id, email=email, name=name or email)
    try:
        # A savepoint, not a bare flush: by the time this runs, the caller
        # (ingest_raw) has already mutated `row` in this same transaction.
        # A plain `session.rollback()` on conflict would discard those
        # mutations and detach every object in the session, silently losing
        # the pipeline's progress -- store_new (Task 10) hit this same class
        # of bug in imap.py and fixed it the same way: only the failed
        # insert's savepoint unwinds.
        async with session.begin_nested():
            session.add(contact)
            await session.flush()
    except IntegrityError:
        # Two messages from a new address arriving together.
        contact = await _find(session, workspace_id, email)
        if contact is None:
            raise
    return contact


DEFAULT_LIMIT = 50


async def list_contacts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Contact], str | None]:
    """Keyset-paginated contacts, newest first.

    Ordered by ``(created_at, id)`` for the same reason the inbox list is:
    the pair keeps the cursor stable when two rows share a timestamp, which
    they will whenever a batch is imported inside one transaction.
    """
    query = sa.select(Contact).where(Contact.workspace_id == workspace_id)

    if cursor:
        try:
            moment, identifier = pagination.decode(cursor)
        except ValueError as error:
            raise Invalid("Invalid cursor.") from error
        query = query.where(
            sa.tuple_(Contact.created_at, Contact.id) < (moment, identifier)
        )

    query = query.order_by(Contact.created_at.desc(), Contact.id.desc()).limit(
        limit + 1
    )
    rows = list(await session.scalars(query))
    next_cursor = (
        pagination.encode(rows[limit - 1].created_at, rows[limit - 1].id)
        if len(rows) > limit
        else None
    )
    return rows[:limit], next_cursor


async def get_contact(
    session: AsyncSession, workspace_id: uuid.UUID, contact_id: uuid.UUID
) -> Contact:
    """Cross-workspace ids raise NotFound, never Forbidden."""
    contact = await session.scalar(
        sa.select(Contact).where(
            Contact.id == contact_id, Contact.workspace_id == workspace_id
        )
    )
    if contact is None:
        raise NotFound("Contact not found.")
    return contact
