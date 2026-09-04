import sqlalchemy as sa

from relaydesk.worker import bridge
from relaydesk.worker.app import app


async def _ping() -> int:
    async with bridge.session_scope() as session:
        return int(await session.scalar(sa.select(sa.literal(1))) or 0)


@app.task(name="relaydesk.ping")
def ping() -> int:
    """Smoke test: proves the worker process can reach Postgres through the
    bridge. Invoked by hand, never scheduled."""
    return bridge.run(_ping())
