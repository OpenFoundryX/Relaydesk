import logging

from relaydesk.config import get_settings
from relaydesk.services import imap
from relaydesk.worker import bridge
from relaydesk.worker.app import app


async def _poll() -> int:
    settings = get_settings()
    mailbox = settings.imap_mailbox
    async with imap.AioImapReader(mailbox) as reader:
        async with bridge.session_scope() as session:
            created = await imap.store_new(session, mailbox, reader)

    for raw_message_id in created:
        ingest_message.delay(str(raw_message_id))
    return len(created)


@app.task(name="relaydesk.imap_poll")
def imap_poll() -> int:
    return bridge.run(_poll())


@app.task(name="relaydesk.ingest_message")
def ingest_message(raw_message_id: str) -> None:
    """Replaced in Task 11. Until then the poller can be exercised on its
    own without messages disappearing into an unregistered task name."""
    logging.getLogger(__name__).info("ingest pending for %s", raw_message_id)
