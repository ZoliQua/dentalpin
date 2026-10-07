"""Membership checks accept members and reject non-members.

Duplicated ``clinic_memberships`` rows used to make existence checks
raise ``MultipleResultsFound`` (#590); since core 0009 the unique
``(clinic_id, user_id)`` constraint makes duplicates impossible, so
these tests pin the checks against single memberships (plus the
constraint itself in ``test_membership_unique.py``).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.service import AppointmentService
from app.modules.schedules.services.professional_hours import ProfessionalHoursService
from app.modules.treatment_plan.service import _validate_professional_in_clinic


async def _professional_member(db_session: AsyncSession, clinic_id) -> User:
    user = User(
        id=uuid4(),
        email=f"dup-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Dup",
        last_name="Member",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role="dentist")
    )
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_treatment_plan_professional_check_accepts_member(
    db_session: AsyncSession, test_clinic: Clinic
):
    doc = await _professional_member(db_session, test_clinic.id)
    await _validate_professional_in_clinic(db_session, test_clinic.id, doc.id)


@pytest.mark.asyncio
async def test_professional_hours_is_professional_accepts_member(
    db_session: AsyncSession, test_clinic: Clinic
):
    doc = await _professional_member(db_session, test_clinic.id)
    assert await ProfessionalHoursService.is_professional(db_session, test_clinic.id, doc.id)


@pytest.mark.asyncio
async def test_agenda_professional_access_accepts_member(
    db_session: AsyncSession, test_clinic: Clinic
):
    doc = await _professional_member(db_session, test_clinic.id)
    assert await AppointmentService.validate_professional_access(db_session, test_clinic.id, doc.id)


@pytest.mark.asyncio
async def test_membership_checks_still_reject_non_members(
    db_session: AsyncSession, test_clinic: Clinic
):
    stranger = uuid4()
    with pytest.raises(ValueError):
        await _validate_professional_in_clinic(db_session, test_clinic.id, stranger)
    assert not await ProfessionalHoursService.is_professional(db_session, test_clinic.id, stranger)
    assert not await AppointmentService.validate_professional_access(
        db_session, test_clinic.id, stranger
    )
