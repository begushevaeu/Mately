from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class DeadlineParseError(ValueError):
    pass


NO_DEADLINE_VALUES = {"нет", "без срока", "без дедлайна", "no", "-"}


def get_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def parse_deadline(value: str, timezone_name: str, now: datetime | None = None) -> datetime | None:
    normalized = value.strip().lower()
    if normalized in NO_DEADLINE_VALUES:
        return None

    tz = get_timezone(timezone_name)
    local_now = now.astimezone(tz) if now is not None else datetime.now(tz)

    if normalized == "сегодня":
        local_deadline = datetime.combine(local_now.date(), time(hour=23, minute=59), tzinfo=tz)
        return local_deadline.astimezone(timezone.utc)

    if normalized == "завтра":
        local_deadline = datetime.combine(local_now.date() + timedelta(days=1), time(hour=23, minute=59), tzinfo=tz)
        return local_deadline.astimezone(timezone.utc)

    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed_date = datetime.strptime(normalized, date_format).date()
            local_deadline = datetime.combine(parsed_date, time(hour=23, minute=59), tzinfo=tz)
            return local_deadline.astimezone(timezone.utc)
        except ValueError:
            continue

    raise DeadlineParseError("Unsupported deadline format")


def format_deadline(deadline: datetime | None, timezone_name: str) -> str:
    if deadline is None:
        return "без срока"

    tz = get_timezone(timezone_name)
    return deadline.astimezone(tz).strftime("%d.%m.%Y")
