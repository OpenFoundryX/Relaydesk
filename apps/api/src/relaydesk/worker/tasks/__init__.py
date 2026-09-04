"""Task modules, imported here so ``app.autodiscover_tasks`` registers them.

``autodiscover_tasks`` (called with ``related_name=None`` in ``app.py``)
imports this package once per worker process; each module below must be
imported here for its ``@app.task`` definitions to register. Later tasks add
their own import to this list.
"""

from relaydesk.worker.tasks import health  # noqa: F401
