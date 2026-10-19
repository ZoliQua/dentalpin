"""Clinic-local calendar dates.

The server runs on UTC (no ``TZ`` in the images), so ``date.today()`` is
the UTC date — a day ahead of a UTC-6 clinic from 18:00 local, a day
behind a UTC+2 clinic until 02:00. Anything that stamps a *calendar*
date a clinic will read (an invoice's issue date, the year in its
number) must ask the clinic's clock instead.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def clinic_today(timezone: str | None) -> date:
    """Today's date in the clinic's IANA ``timezone`` (UTC if unknown)."""
    try:
        tz = ZoneInfo(timezone) if timezone else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()
