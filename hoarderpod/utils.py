"""
Utility functions for the application
"""

from datetime import datetime, timezone


def oxford_join(items: list[str]) -> str:
    """Join a list of items with commas and "and".

    Args:
        items: The list of items to join

    Returns:
        str: The joined items
    """
    if not items:
        return ""
    if len(items) == 1:
        return str(items[0])
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"

    return f"{', '.join(items[:-1])}, and {items[-1]}"


def to_local_datetime(input_date: str) -> datetime:
    """Convert a date string to a local datetime

    Args:
        input_date: The date string to convert

    Returns:
        datetime: The local datetime
    """
    LOCAL_TIMEZONE = datetime.now(timezone.utc).astimezone().tzinfo
    return datetime.strptime(input_date, "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE) if input_date else None


def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC.

    Args:
        dt: The datetime to convert

    Returns:
        datetime: The UTC datetime
    """
    return dt.replace(tzinfo=timezone.utc)


def horder_dt_to_py(horder_datetime: str) -> datetime:
    """Convert a Hoarder datetime to a Python datetime.

    Args:
        horder_datetime: The Hoarder datetime
    """
    return datetime.strptime(horder_datetime, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
