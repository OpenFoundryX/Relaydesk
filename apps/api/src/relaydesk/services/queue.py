"""The one place service code hands work to Celery.

Kept as a module of plain functions so tests can monkeypatch a single name
instead of standing up a broker, and so services never import Celery
directly — which would make importing any service pull in the worker.
"""


def enqueue_system_email(
    to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    from relaydesk.worker.tasks.mail import send_system_email

    send_system_email.delay(to, subject, text_body, html_body)
