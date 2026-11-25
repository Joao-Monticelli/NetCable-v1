"""Current time in UTC without time zone (how the database stores dates).

Same value as the deprecated datetime.utcnow(), without the deprecation.
"""

from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)
