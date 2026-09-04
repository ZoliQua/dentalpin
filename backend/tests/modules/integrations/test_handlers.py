"""IntegrationsHandlers: transactional enqueue for all supported triggers."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password
from app.modules.integrations.handlers import IntegrationsHandlers
from app.modules.integrations.models import WebhookDelivery, WebhookSubscription

EVENT = "patient.created"


async def _subscription(db, clinic_id, *, event_types=(EVENT,)):
    sub = WebhookSubscription(
        clinic_id=clinic_id,
        target_url="https://example.com/hook",
        event_types=list(event_types),
        secret_encrypted=encrypt_password("whsec"),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


@pytest.mark.asyncio
async def test_on_patient_created_enqueues_delivery(db_session: AsyncSession, test_clinic):
    await _subscription(db_session, test_clinic.id)

    await IntegrationsHandlers.on_patient_created(
        {"clinic_id": str(test_clinic.id), "patient_id": "p1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_type == EVENT
    assert rows[0].payload["clinic_id"] == str(test_clinic.id)
    assert rows[0].payload["patient_id"] == "p1"
    assert "occurred_at" in rows[0].payload


@pytest.mark.asyncio
async def test_on_patient_created_no_subscription_no_delivery(
    db_session: AsyncSession, test_clinic
):
    await IntegrationsHandlers.on_patient_created(
        {"clinic_id": str(test_clinic.id), "patient_id": "p1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_on_patient_created_malformed_payload_does_not_raise(
    db_session: AsyncSession, test_clinic
):
    # Missing clinic_id: must log and return, never propagate — a handler
    # error must not fail the publisher's own transaction (issue #183
    # reasoning notifications/handlers.py already documents).
    await IntegrationsHandlers.on_patient_created({"patient_id": "p1"}, db=db_session)

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_rollback_of_outer_transaction_discards_queued_delivery(
    db_session: AsyncSession, test_clinic
):
    """A rolled-back publisher transaction must queue nothing — the whole
    point of the transactional handler shape (ADR 0019)."""
    await _subscription(db_session, test_clinic.id)

    await IntegrationsHandlers.on_patient_created(
        {"clinic_id": str(test_clinic.id), "patient_id": "p1"}, db=db_session
    )
    # Simulate the publisher's own transaction failing after the handler ran,
    # before it ever commits.
    await db_session.rollback()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []


APPOINTMENT_EVENT = "appointment.completed"


@pytest.mark.asyncio
async def test_on_appointment_completed_enqueues_delivery(db_session: AsyncSession, test_clinic):
    await _subscription(db_session, test_clinic.id, event_types=(APPOINTMENT_EVENT,))

    await IntegrationsHandlers.on_appointment_completed(
        {"clinic_id": str(test_clinic.id), "appointment_id": "a1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_type == APPOINTMENT_EVENT
    assert rows[0].payload["clinic_id"] == str(test_clinic.id)
    assert rows[0].payload["appointment_id"] == "a1"
    assert "occurred_at" in rows[0].payload


@pytest.mark.asyncio
async def test_on_appointment_completed_no_subscription_no_delivery(
    db_session: AsyncSession, test_clinic
):
    await IntegrationsHandlers.on_appointment_completed(
        {"clinic_id": str(test_clinic.id), "appointment_id": "a1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_on_appointment_completed_malformed_payload_does_not_raise(
    db_session: AsyncSession, test_clinic
):
    await IntegrationsHandlers.on_appointment_completed({"appointment_id": "a1"}, db=db_session)

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []


@pytest.mark.parametrize(
    "event_type,handler_name,payload_extra",
    [
        ("appointment.scheduled", "on_appointment_scheduled", {"appointment_id": "a2"}),
        ("appointment.cancelled", "on_appointment_cancelled", {"appointment_id": "a2"}),
        ("appointment.no_show", "on_appointment_no_show", {"appointment_id": "a2"}),
        ("budget.sent", "on_budget_sent", {"budget_id": "b1"}),
        ("budget.accepted", "on_budget_accepted", {"budget_id": "b1"}),
        ("budget.rejected", "on_budget_rejected", {"budget_id": "b1"}),
    ],
)
@pytest.mark.asyncio
async def test_phase2_trigger_enqueues_delivery(
    db_session: AsyncSession,
    test_clinic,
    event_type: str,
    handler_name: str,
    payload_extra: dict,
):
    await _subscription(db_session, test_clinic.id, event_types=(event_type,))

    handler = getattr(IntegrationsHandlers, handler_name)
    await handler({"clinic_id": str(test_clinic.id), **payload_extra}, db=db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_type == event_type
    assert rows[0].payload["clinic_id"] == str(test_clinic.id)
    assert "occurred_at" in rows[0].payload


@pytest.mark.asyncio
async def test_shared_event_id_across_subscriptions(db_session: AsyncSession, test_clinic):
    """All deliveries queued for the same handler call share event_id (issue #65 §1)."""
    await _subscription(db_session, test_clinic.id)
    await _subscription(db_session, test_clinic.id)

    await IntegrationsHandlers.on_patient_created(
        {"clinic_id": str(test_clinic.id), "patient_id": "p1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 2
    event_ids = {r.event_id for r in rows}
    assert len(event_ids) == 1
    assert rows[0].event_id is not None


@pytest.mark.asyncio
async def test_on_appointment_completed_does_not_cross_deliver_to_patient_created_sub(
    db_session: AsyncSession, test_clinic
):
    """A subscription for patient.created only must not receive an
    appointment.completed delivery — event-type filtering, not just
    clinic filtering."""
    await _subscription(db_session, test_clinic.id, event_types=(EVENT,))

    await IntegrationsHandlers.on_appointment_completed(
        {"clinic_id": str(test_clinic.id), "appointment_id": "a1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []
