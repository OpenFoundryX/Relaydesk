import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models import Label, LabelColor

PALETTE = [
    LabelColor.citron,
    LabelColor.slate,
    LabelColor.amber,
    LabelColor.rose,
    LabelColor.sky,
]


async def list_labels(session: AsyncSession, workspace_id: uuid.UUID) -> list[Label]:
    return list(
        await session.scalars(
            sa.select(Label)
            .where(Label.workspace_id == workspace_id)
            .order_by(Label.name)
        )
    )


async def create_label(
    session: AsyncSession, workspace_id: uuid.UUID, name: str
) -> Label:
    """Idempotent by name, so a double submit returns the existing label."""
    trimmed = name.strip()
    if not trimmed:
        raise Invalid("A label needs a name.")

    # ``name`` is CITEXT, so this comparison is already case-insensitive at
    # the database level — no ``func.lower()`` needed, and the column's
    # unique constraint (workspace_id, name) rejects a case-variant
    # duplicate too, rather than silently accepting both "Billing" and
    # "billing".
    existing = await session.scalar(
        sa.select(Label).where(
            Label.workspace_id == workspace_id, Label.name == trimmed
        )
    )
    if existing is not None:
        return existing

    count = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Label)
        .where(Label.workspace_id == workspace_id)
    )
    label = Label(
        workspace_id=workspace_id,
        name=trimmed,
        color=PALETTE[(count or 0) % len(PALETTE)],
    )
    session.add(label)
    await session.commit()
    return label
