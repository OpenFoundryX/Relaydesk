import uuid

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.contact import Contact


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
