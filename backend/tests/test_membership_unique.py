"""Unique membership per clinic+user (#590 follow-up).

Duplicated rows made membership checks blow up and the effective role
ambiguous. The model carries the constraint; 0009 backfills old dupes.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User


@pytest.mark.asyncio
async def test_duplicate_membership_rejected(db_session: AsyncSession, test_clinic: Clinic) -> None:
    """A second row for the same user+clinic violates the constraint."""
    user = (
        await db_session.execute(select(User).where(User.email == "test@example.com"))
    ).scalar_one()
    db_session.add(ClinicMembership(user_id=user.id, clinic_id=test_clinic.id, role="dentist"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
