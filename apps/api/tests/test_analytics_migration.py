import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

INDEXES = [
    ("activity_events", "ix_activity_events_workspace_kind_at"),
    ("messages", "ix_messages_workspace_direction_sent_at"),
]


async def test_the_analytics_indexes_exist(db_session: AsyncSession) -> None:
    """Every analytics query filters one of these two tables by workspace and
    a time column. Without the indexes each card is a sequential scan."""
    for table, index in INDEXES:
        found = await db_session.scalar(
            sa.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = :table AND indexname = :index"
            ),
            {"table": table, "index": index},
        )
        assert found == index, f"{index} missing from {table}"
