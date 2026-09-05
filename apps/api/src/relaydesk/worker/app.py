from celery import Celery
from celery.signals import worker_process_init

from relaydesk.config import get_settings
from relaydesk.worker import bridge

settings = get_settings()

app = Celery("relaydesk", broker=settings.celery_broker_url)

app.conf.update(
    # These are fire-and-forget jobs; a result backend would add Redis for
    # results nothing reads.
    task_ignore_result=True,
    # Acknowledge after the task finishes, not on receipt, so a worker killed
    # mid-send redelivers rather than silently dropping the mail. This is what
    # makes idempotency load-bearing: see the dedupe indexes in Task 3.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="relaydesk",
    timezone="UTC",
    beat_schedule={
        "poll-inbound-mail": {
            "task": "relaydesk.imap_poll",
            "schedule": float(settings.imap_poll_seconds),
        },
        "reconcile-outbound": {
            "task": "relaydesk.reconcile_outbound",
            "schedule": 300.0,
        },
        "reconcile-inbound": {
            "task": "relaydesk.reconcile_inbound",
            "schedule": 300.0,
        },
    },
)

app.autodiscover_tasks(["relaydesk.worker.tasks"], related_name=None, force=True)


@worker_process_init.connect
def _init_process(**_kwargs: object) -> None:
    bridge.init_worker_process()
