from datetime import timedelta

from relaydesk.services import ratelimit
from relaydesk.worker import bridge
from relaydesk.worker.app import app

# The longest window any caller of `ratelimit.check` uses is one hour (the
# portal's `ticket_ip_hourly_cap`). A day is a deliberately generous
# multiple of that: rows this old cannot affect any count, and keeping the
# margin wide means adding a longer-windowed limit later does not silently
# start deleting rows that still matter.
RETENTION = timedelta(days=1)


async def _sweep() -> int:
    async with bridge.session_scope() as session:
        return await ratelimit.sweep(session, RETENTION)


@app.task(name="relaydesk.sweep_rate_limits")
def sweep_rate_limits() -> int:
    """Drop rate-limit hits too old to count against any window.

    Nothing else deletes them, and every allowed call adds one -- including
    every submission caught by the portal's honeypot, which is answered
    with a fake success and so leaves nothing else behind. Without this the
    table grows forever and its lookup index with it.
    """
    return bridge.run(_sweep())
