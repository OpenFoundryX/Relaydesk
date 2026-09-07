"""Keyset cursors, shared by every paginated list.

A cursor is an opaque base64 of ``<timestamp>|<uuid>``. The pair is what
makes the cursor stable when two rows share a timestamp, which is why the
uuid is in there at all.

Extracted from ``services.conversations`` when contacts became the second
list to need it. Callers keep their own encode function so each list names
the timestamp column it orders by; only the format lives here.
"""

import base64
import uuid
from datetime import datetime


def encode(moment: datetime, identifier: uuid.UUID) -> str:
    raw = f"{moment.isoformat()}|{identifier}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Raises ``ValueError`` on anything malformed.

    ``binascii.Error`` and ``UnicodeDecodeError`` both subclass ``ValueError``,
    so a bad base64 payload arrives here as one error type and callers can
    turn it into a single ``Invalid``.
    """
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    moment, identifier = raw.split("|", 1)
    return datetime.fromisoformat(moment), uuid.UUID(identifier)
