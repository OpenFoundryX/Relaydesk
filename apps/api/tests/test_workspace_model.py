import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Workspace


async def test_workspace_persists_with_defaults(db_session: AsyncSession) -> None:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    db_session.add(workspace)
    await db_session.commit()

    stored = await db_session.scalar(
        sa.select(Workspace).where(Workspace.slug == "chronon")
    )

    assert stored is not None
    assert stored.id is not None
    assert stored.conversation_seq == 0
    assert stored.timezone == "UTC"
    assert stored.created_at is not None


async def test_workspace_slug_is_unique(db_session: AsyncSession) -> None:
    db_session.add(Workspace(name="A", slug="dup", monogram="A"))
    await db_session.commit()

    db_session.add(Workspace(name="B", slug="dup", monogram="B"))
    try:
        await db_session.commit()
    except sa.exc.IntegrityError:
        return
    raise AssertionError("expected a unique-constraint violation on workspaces.slug")
