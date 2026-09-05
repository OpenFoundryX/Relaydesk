"""The one place service code hands work to Celery.

Kept as a module of plain functions so tests can monkeypatch a single name
instead of standing up a broker, and so services never import Celery
directly — which would make importing any service pull in the worker.
"""

import logging
import uuid

logger = logging.getLogger(__name__)


def enqueue_system_email(
    to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    from relaydesk.worker.tasks.mail import send_system_email

    # .delay() talks to the broker synchronously and can raise (e.g. RabbitMQ
    # unreachable). By the time a caller enqueues system mail, the operation
    # it's about (an assignment, a reply) has already committed, so failing
    # the request here would report an error for something that actually
    # succeeded. Swallowing this one call is correct: for system mail the
    # alternative is a spurious 500; for Task 13's outbound replies, a
    # message stuck in `queued` is picked up by the Beat reconciler.
    try:
        send_system_email.delay(to, subject, text_body, html_body)
    except Exception:
        logger.warning(
            "Failed to enqueue relaydesk.send_system_email for %s", to, exc_info=True
        )


def enqueue_reply(message_id: uuid.UUID) -> None:
    from relaydesk.worker.tasks.mail import send_conversation_message

    # Same reasoning as enqueue_system_email above, doubly so here: the
    # message row is already committed as `queued`, so a broker hiccup must
    # not surface as a failed reply. reconcile_outbound republishes it.
    try:
        send_conversation_message.delay(str(message_id))
    except Exception:
        logger.warning(
            "could not publish relaydesk.send_conversation_message for %s",
            message_id,
            exc_info=True,
        )
