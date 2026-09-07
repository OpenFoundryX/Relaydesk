from datetime import timedelta

from relaydesk.services import api_usage, ratelimit
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


# One minute is the only window ``api_usage.charge`` uses. A day is a
# deliberately generous multiple: a window this old cannot affect any count,
# and the margin means a longer window added later does not silently start
# deleting rows that still matter.
API_USAGE_RETENTION = timedelta(days=1)


async def _sweep_api_usage() -> int:
    async with bridge.session_scope() as session:
        return await api_usage.sweep(session, API_USAGE_RETENTION)


@app.task(name="relaydesk.sweep_api_usage")
def sweep_api_usage() -> int:
    """Drop rate-limit windows too old to count against any limit.

    One row per key per minute is small, but nothing else deletes it, and
    over a year an active key leaves half a million rows behind.
    """
    return bridge.run(_sweep_api_usage())
