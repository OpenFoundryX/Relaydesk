import uuid

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.contact import Contact


async def upsert(
    session: AsyncSession, workspace_id: uuid.UUID, email: str, name: str
) -> Contact:
    """Find or create a contact. ``contacts.email`` is CITEXT, so lookup is
    already case-insensitive."""
    contact = await session.scalar(
        sa.select(Contact).where(
            Contact.workspace_id == workspace_id, Contact.email == email
        )
    )
    if contact is not None:
        # A later message may carry a better display name than the first did.
        if name and contact.name != name and "@" in contact.name:
            contact.name = name
        return contact

    contact = Contact(workspace_id=workspace_id, email=email, name=name or email)
    session.add(contact)
    try:
        await session.flush()
    except IntegrityError:
        # Two messages from a new address arriving together.
        await session.rollback()
        contact = await session.scalar(
            sa.select(Contact).where(
                Contact.workspace_id == workspace_id, Contact.email == email
            )
        )
        if contact is None:
            raise
    return contact
