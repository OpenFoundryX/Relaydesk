"""One shared IANA time-zone check.

Both a workspace's zone and a user's own are stored as plain strings and
later handed to ``ZoneInfo``, so both need the same guard at the point they
are written. Kept here rather than on either service so neither owns the
other's validation.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from relaydesk.errors import Invalid

# ``users.timezone`` and ``workspaces.timezone`` are both String(64). An
# over-length value would otherwise reach the column and raise
# StringDataRightTruncation deep in a commit -- a 500 for what is a bad
# request. No IANA name comes close to this.
MAX_LENGTH = 64


def valid_timezone(value: str) -> str:
    """Reject anything ``ZoneInfo`` cannot load.

    Every conversation, message and activity serializer resolves a stored
    timezone with ``ZoneInfo(...)``. An unvalidated string would therefore
    500 the whole inbox for whoever it applies to until someone corrected
    it in the database, so the bad value never reaches the column.
    """
    if len(value) > MAX_LENGTH:
        raise Invalid("That is not a recognised IANA time zone.")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise Invalid("That is not a recognised IANA time zone.") from error
    return value
