from datetime import date, datetime, timezone
from typing import Annotated
from pydantic import BeforeValidator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def calendar_date(value):
    if isinstance(value,str):
        parsed=date.fromisoformat(value)
        if parsed.isoformat()!=value:raise ValueError('Use YYYY-MM-DD')
        return parsed
    if type(value) is not date:raise ValueError('Use a calendar date')
    return value


CalendarDate=Annotated[date,BeforeValidator(calendar_date)]


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
