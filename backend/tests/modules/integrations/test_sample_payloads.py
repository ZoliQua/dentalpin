"""Frozen sample payloads: catalog coverage + clinic_id parseable."""

from uuid import UUID

import pytest

from app.modules.integrations.sample_payload_loader import all_sample_payloads, load_sample_payload
from app.modules.integrations.triggers import SUPPORTED_EVENT_TYPES


def test_every_supported_event_has_a_sample_file():
    payloads = all_sample_payloads()
    missing = SUPPORTED_EVENT_TYPES - set(payloads)
    assert not missing, f"Missing sample payload files for: {sorted(missing)}"


def test_no_orphan_sample_files():
    """Every sample file maps to an event in SUPPORTED_EVENT_TYPES."""
    payloads = all_sample_payloads()
    orphans = set(payloads) - SUPPORTED_EVENT_TYPES
    assert not orphans, f"Sample files exist for unsupported events: {sorted(orphans)}"


@pytest.mark.parametrize("event_type", sorted(SUPPORTED_EVENT_TYPES))
def test_sample_payload_clinic_id_is_valid_uuid(event_type: str):
    payload = load_sample_payload(event_type)
    assert "clinic_id" in payload, f"{event_type}: missing clinic_id — _enqueue won't scope it"
    UUID(payload["clinic_id"])
