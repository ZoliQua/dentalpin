"""Event handlers for the integrations module.

Transactional (ADR 0019), matching notifications/handlers.py exactly:
each body queues WebhookDelivery rows on the publisher's own session —
DB-only, no network I/O. The scheduled dispatch tick owns the network
I/O, so a rolled-back request queues no delivery.

Phase 1 shipped two triggers end-to-end (issue #65); Phase 2 adds the
concrete-appointment and budget workflow set (all publishers pass their
session via ``db=``, satisfying the ADR 0019 guard test). Every handler
is identical apart from which ``EventType`` it enqueues for, so they
all share ``_enqueue``.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IntegrationsHandlers:
    """Event handlers for webhook trigger events.

    All handlers are identical apart from which ``EventType`` they
    enqueue for, so they share ``_enqueue`` rather than duplicating
    the transactional/error-handling shape per trigger.
    """

    @staticmethod
    async def _enqueue(event_type: str, data: dict[str, Any], *, db: AsyncSession) -> None:
        """Queue a delivery for every subscription listing ``event_type``.

        Transactional (ADR 0019): queues on the publisher's session, no
        network I/O here — the outbox tick does the sending. A handler
        error must not fail the publisher's own transaction (same
        reasoning notifications/handlers.py documents), so a malformed
        payload is logged and swallowed, never raised.

        ``event_id`` (issue #65 §1) is generated once per publish here,
        so every delivery queued across all matching subscriptions for
        this one event shares it — a receiver can dedupe.
        """
        from .gateway import WebhookGateway

        try:
            clinic_id = UUID(data["clinic_id"])
        except (KeyError, ValueError) as exc:
            logger.error("integrations: malformed %s payload: %s", event_type, exc)
            return

        # occurred_at: stamped here rather than trusting the publisher's own
        # payload to carry one, since not every EventType payload does.
        payload = {**data, "occurred_at": datetime.now(UTC).isoformat()}

        async with db.begin_nested():
            await WebhookGateway.enqueue_for_event(
                db, clinic_id, event_type, payload, event_id=uuid4()
            )

    @staticmethod
    async def on_patient_created(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.PATIENT_CREATED, data, db=db)

    @staticmethod
    async def on_appointment_completed(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.APPOINTMENT_COMPLETED, data, db=db)

    @staticmethod
    async def on_appointment_scheduled(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.APPOINTMENT_SCHEDULED, data, db=db)

    @staticmethod
    async def on_appointment_cancelled(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.APPOINTMENT_CANCELLED, data, db=db)

    @staticmethod
    async def on_appointment_no_show(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.APPOINTMENT_NO_SHOW, data, db=db)

    @staticmethod
    async def on_budget_sent(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.BUDGET_SENT, data, db=db)

    @staticmethod
    async def on_budget_accepted(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.BUDGET_ACCEPTED, data, db=db)

    @staticmethod
    async def on_budget_rejected(data: dict[str, Any], *, db: AsyncSession) -> None:
        from app.core.events import EventType

        await IntegrationsHandlers._enqueue(EventType.BUDGET_REJECTED, data, db=db)
