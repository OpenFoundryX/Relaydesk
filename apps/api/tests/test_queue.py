import logging

from relaydesk.services import queue
from relaydesk.worker.tasks.mail import send_system_email


def test_a_broker_failure_does_not_propagate(monkeypatch, caplog) -> None:
    """By the time we enqueue system mail, the operation it's about has
    already committed. A broker hiccup must not turn that into a 500 for
    the caller — see services/queue.py."""

    def raise_broker_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(send_system_email, "delay", raise_broker_error)
    # migrations/env.py calls logging.config.fileConfig(), which (by its
    # default disable_existing_loggers=True) disables every logger that
    # already existed at that point — including this module's, created at
    # import time — for the rest of the process. In the full suite, an
    # earlier test's db_session triggers the one-time migration run before
    # this test executes, so without this the warning below is silently
    # dropped rather than merely mis-leveled.
    monkeypatch.setattr(queue.logger, "disabled", False)

    with caplog.at_level(logging.WARNING):
        queue.enqueue_system_email("ada@example.com", "Hello", "Hi")

    assert "relaydesk.send_system_email" in caplog.text
    assert "ada@example.com" in caplog.text
