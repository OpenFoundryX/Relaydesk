import logging
import uuid
from datetime import timedelta

from relaydesk.services import ingest, mailer, outbound
from relaydesk.worker import bridge
from relaydesk.worker.app import app
from relaydesk.worker.tasks.inbound import ingest_message

logger = logging.getLogger(__name__)


@app.task(
    name="relaydesk.send_system_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def send_system_email(
    to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    bridge.run(
        mailer.send(
            to=to,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            headers=mailer.system_headers(),
        )
    )


async def _deliver(message_id: uuid.UUID) -> str:
    async with bridge.session_scope() as session:
        return str(await outbound.deliver(session, message_id))


async def _mark_failed(message_id: uuid.UUID, error: str) -> None:
    async with bridge.session_scope() as session:
        await outbound.mark_failed(session, message_id, error)


async def _requeue_stalled() -> list[uuid.UUID]:
    async with bridge.session_scope() as session:
        return await outbound.requeue_stalled(session, timedelta(minutes=2))


async def _requeue_unprocessed() -> list[uuid.UUID]:
    async with bridge.session_scope() as session:
        return await ingest.requeue_unprocessed(session, timedelta(minutes=2))


@app.task(
    name="relaydesk.send_conversation_message",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=900,
    max_retries=6,
)
def send_conversation_message(self, message_id: str) -> str:
    """Greylisting rejects a first delivery attempt by design, so a transient
    failure here is normal rather than exceptional — hence the backoff."""
    identifier = uuid.UUID(message_id)
    try:
        return str(bridge.run(_deliver(identifier)))
    except Exception as error:
        if self.request.retries >= self.max_retries:
            bridge.run(_mark_failed(identifier, str(error)))
        raise


@app.task(name="relaydesk.reconcile_outbound")
def reconcile_outbound() -> int:
    stalled = bridge.run(_requeue_stalled())
    for message_id in stalled:
        # One broker hiccup mid-loop must not abandon the rest of this
        # cycle's stalled messages -- the next tick would still catch them,
        # but there's no reason to let a single failed publish cost the
        # others when the guard is this cheap.
        try:
            send_conversation_message.delay(str(message_id))
        except Exception:
            logger.warning(
                "could not republish relaydesk.send_conversation_message for %s",
                message_id,
                exc_info=True,
            )
    return len(stalled)


@app.task(name="relaydesk.reconcile_inbound")
def reconcile_inbound() -> int:
    """Re-enqueue raw messages the poller stored but never got onto the broker.

    ``imap_poll`` writes ``raw_messages`` rows and then publishes one
    ``ingest_message`` per row. The publish is not part of that transaction, and
    the queue seam swallows broker failures by design, so a RabbitMQ outage
    leaves rows sitting in ``fetched`` with nothing to pick them up. Without
    this, that mail is silently never ingested — the bytes are safe in the
    landing zone but no ticket is ever created.
    """
    stuck = bridge.run(_requeue_unprocessed())
    for raw_message_id in stuck:
        try:
            ingest_message.delay(str(raw_message_id))
        except Exception:
            logger.warning(
                "could not republish relaydesk.ingest_message for %s",
                raw_message_id,
                exc_info=True,
            )
    return len(stuck)
