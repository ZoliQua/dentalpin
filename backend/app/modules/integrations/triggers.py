"""Event types and API token scopes this module actually supports.

The trigger catalog covers the transactional publishers on the bus
(issue #65 §3). Almost every other event #65 wants already exists there
(``core/events/types.py``) — adding it here means only "declare a new
transactional handler in handlers.py", no new bus infra. Keeping this
list separate from ``EventType`` (which has ~60 events, most
irrelevant to webhooks) is what lets ``WebhookSubscriptionCreate``
reject a subscription for an event nobody will ever deliver, instead
of silently accepting one that never fires.

``SUPPORTED_TOKEN_SCOPES`` is the same idea for API tokens: no
consumer endpoint checks scopes yet (the public data-read API is
follow-up scope), but validating against a closed catalog now means
we never have to migrate free-text scopes later once one exists.
"""

from app.core.events import EventType

SUPPORTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventType.PATIENT_CREATED,
        EventType.APPOINTMENT_SCHEDULED,
        EventType.APPOINTMENT_COMPLETED,
        EventType.APPOINTMENT_CANCELLED,
        EventType.BUDGET_ACCEPTED,
        EventType.INVOICE_SENT,
    }
)

# Frozen sample payload per trigger (issue #65 §3): the stable fields a
# Zapier/Make visual mapper binds against. Single source of truth — the
# catalog endpoint serves these, and a test pins every supported trigger
# to a sample whose keys mirror the real publisher payload. Adding a key
# to a publisher payload is fine; renaming/removing one is a breaking
# change to every Zap in the wild.
SAMPLE_PAYLOADS: dict[str, dict] = {
    EventType.PATIENT_CREATED: {
        "patient_id": "0b0e2a1e-4f6a-4d38-9c53-1f4b7e2ad001",
        "clinic_id": "7a1d2c3b-89ab-4cde-9012-3456789abc02",
        "occurred_at": "2026-08-31T09:00:00+00:00",
    },
    EventType.APPOINTMENT_SCHEDULED: {
        "appointment_id": "c2b4a6d8-1357-4f9b-8ace-024680bdf003",
        "clinic_id": "7a1d2c3b-89ab-4cde-9012-3456789abc02",
        "patient_id": "0b0e2a1e-4f6a-4d38-9c53-1f4b7e2ad001",
        "professional_id": "d4e5f6a7-2468-4ace-b135-79bdf0246004",
        "start_time": "2026-09-01T10:00:00+00:00",
        "end_time": "2026-09-01T10:30:00+00:00",
        "treatment_type": "revision",
        "cabinet": "1",
        "occurred_at": "2026-08-31T09:00:00+00:00",
    },
    EventType.APPOINTMENT_COMPLETED: {
        "appointment_id": "c2b4a6d8-1357-4f9b-8ace-024680bdf003",
        "clinic_id": "7a1d2c3b-89ab-4cde-9012-3456789abc02",
        "patient_id": "0b0e2a1e-4f6a-4d38-9c53-1f4b7e2ad001",
        "occurred_at": "2026-08-31T09:00:00+00:00",
    },
    EventType.APPOINTMENT_CANCELLED: {
        "appointment_id": "c2b4a6d8-1357-4f9b-8ace-024680bdf003",
        "clinic_id": "7a1d2c3b-89ab-4cde-9012-3456789abc02",
        "patient_id": "0b0e2a1e-4f6a-4d38-9c53-1f4b7e2ad001",
        "occurred_at": "2026-08-31T09:00:00+00:00",
    },
    EventType.BUDGET_ACCEPTED: {
        "clinic_id": "7a1d2c3b-89ab-4cde-9012-3456789abc02",
        "budget_id": "e6f7a8b9-3579-4bdf-9ace-13579bdf0005",
        "patient_id": "0b0e2a1e-4f6a-4d38-9c53-1f4b7e2ad001",
        "budget_number": "P-2026-0042",
        "total": "1250.00",
        "accepted_by": "d4e5f6a7-2468-4ace-b135-79bdf0246004",
        "accepted_via": "staff",
        "plan_id": None,
        "occurred_at": "2026-08-31T09:00:00+00:00",
    },
    EventType.INVOICE_SENT: {
        "clinic_id": "7a1d2c3b-89ab-4cde-9012-3456789abc02",
        "invoice_id": "f8a9b0c1-468a-4ce0-8bdf-2468ace00006",
        "patient_id": "0b0e2a1e-4f6a-4d38-9c53-1f4b7e2ad001",
        "send_method": "email",
        "recipient_email": "patient@example.com",
        "occurred_at": "2026-08-31T09:00:00+00:00",
    },
}

SUPPORTED_TOKEN_SCOPES: frozenset[str] = frozenset({"patients:read"})
