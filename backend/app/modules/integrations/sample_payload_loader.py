"""Frozen sample payloads for every supported webhook trigger.

The JSON blobs in ``sample_payloads/`` are the *canonical* delivery
payloads for each ``SUPPORTED_EVENT_TYPES`` member (issue #65 §3) —
frozen so a receiver/Zapier step can be built against a stable shape,
and so the test suite can assert that the module's handlers don't
randomly change the envelope. Each file is named ``<event>.json`` and
mirrors the publisher's own ``event_bus.publish`` payload (minus the
``occurred_at`` the gateway stamps).

Tests assert coverage (every supported event has a file) and that each
file's ``clinic_id`` parses (handlers enqueue per-clinic off it) — so
adding a trigger without a frozen payload, or freezing one the gateway
can't scope, fails CI.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .triggers import SUPPORTED_EVENT_TYPES


def load_sample_payload(event_type: str) -> dict[str, Any]:
    """Return the frozen sample payload for ``event_type``.

    Raises ``FileNotFoundError`` for unknown/missing events — tests treat
    that as a catalog-consistency failure.
    """
    path = resources.files(__package__).joinpath("sample_payloads").joinpath(f"{event_type}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def all_sample_payloads() -> dict[str, dict[str, Any]]:
    """``{event_type: payload}`` for every event with a frozen file."""
    seen_dir = resources.files(__package__).joinpath("sample_payloads")
    known: dict[str, dict[str, Any]] = {}
    for event_type in SUPPORTED_EVENT_TYPES:
        file = seen_dir.joinpath(f"{event_type}.json")
        if file.is_file():
            known[event_type] = json.loads(file.read_text(encoding="utf-8"))
    return known
