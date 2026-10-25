"""Clinic-local calendar dates.

The server runs on UTC (no ``TZ`` in the images), so ``date.today()`` is
the UTC date — a day ahead of a UTC-6 clinic from 18:00 local, a day
behind a UTC+2 clinic until 02:00. Anything that stamps a *calendar*
date a clinic will read (an invoice's issue date, the year in its
number) must ask the clinic's clock instead.
"""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic


def clinic_today(timezone: str | None) -> date:
    """Today's date in the clinic's IANA ``timezone`` (UTC if unknown)."""
    try:
        tz = ZoneInfo(timezone) if timezone else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


async def clinic_today_for(db: AsyncSession, clinic_id: UUID) -> date:
    """``clinic_today`` for a clinic known only by id (one indexed read)."""
    timezone = await db.scalar(select(Clinic.timezone).where(Clinic.id == clinic_id))
    return clinic_today(timezone)
