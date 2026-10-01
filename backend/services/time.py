from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def local_today(timezone_name, *, now=None):
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('An instant must have a timezone')
    return instant.astimezone(ZoneInfo(timezone_name)).date()


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError('Invalid IANA timezone') from None
    return value
