import uuid

from relaydesk.config import get_settings
from relaydesk.services import imap, ingest
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


@app.task(
    name="relaydesk.ingest_message",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def ingest_message(raw_message_id: str) -> str:
    return bridge.run(_ingest(uuid.UUID(raw_message_id)))


async def _ingest(raw_message_id: uuid.UUID) -> str:
    async with bridge.session_scope() as session:
        return str(await ingest.ingest_raw(session, raw_message_id))
