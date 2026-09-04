"""Guard rails for the catalog generator (workflow-infra Phase 1).

Regression cover for the file-level-only publisher anchors: the committed
events catalog must never embed absolute line numbers, because an unrelated
edit above a ``event_bus.publish`` callsite would shift the line and make
``catalog-freshness`` fail on a no-op diff (the 484→486 drift class).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_catalogs as gc  # noqa: E402


def _fake_publishers() -> dict[str, list[tuple[str, str, int]]]:
    return {
        "patient.created": [("patients", "backend/app/modules/patients/service.py", 404)],
    }


def test_events_catalog_renders_file_anchor_without_line_number() -> None:
    text = gc._render_events_catalog([], _fake_publishers())
    assert "backend/app/modules/patients/service.py" in text
    assert "service.py:404" not in text
    assert not re.search(r"\.py:\d+", text)


def test_events_catalog_detail_keeps_publisher_row() -> None:
    text = gc._render_events_catalog([], _fake_publishers())
    detail = text.split("## Detail", 1)[1]
    assert "- `patients` — `backend/app/modules/patients/service.py`" in detail


def test_publisher_scan_still_computes_line_for_feral_gate() -> None:
    # ``--check`` reports a `file=,line=` for feral events; the tuples must
    # keep the line number even though the committed render drops it.
    publishers = gc._scan_publishers()
    assert publishers, "expected at least one publish callsite in the tree"
    for sites in publishers.values():
        for module_name, relpath, lineno in sites:
            assert isinstance(lineno, int) and lineno >= 1
            assert module_name
            assert relpath.endswith(".py")
