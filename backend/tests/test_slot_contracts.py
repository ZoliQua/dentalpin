"""Every ``registerSlot('name')`` targets a slot somebody renders.

A slot name is an untyped string on both sides: a module layer calls
``registerSlot('patient.summary.cards', …)`` and a host page calls
``resolve('patient.summary.cards', ctx)``. Nothing connects the two but
the spelling, and a registration into a name no host resolves fails
silently — the component is never mounted, no warning is logged, and the
module's feature is simply absent from the UI. ``SlotEntry.permission``
already got the opposite treatment in #557 ("Typed as ``PermissionValue``
so renames fail at typecheck"); the slot name itself did not.

This has happened twice in the tree: the orphaned ``VisitSummaryCard.vue``
deleted in #182 ("never mounted"), and the ``reports.categories`` entry
below. One of those was found by reading, not by CI.

The scan is static and deliberately literal: it only sees
``registerSlot('…')`` with a string literal and only credits consumers
that name the slot literally. A dynamic name would be invisible to it —
and would be worth a comment on the registration explaining why.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Slot names that are registered on purpose while no host renders them.
# Each entry needs the reason and where the decision is written down —
# "it does not render" is not by itself a reason.
DORMANT_SLOTS: dict[str, str] = {
    # reports/CLAUDE.md marks this one "Deprecated — kept for backwards
    # compatibility only… any registered consumer becomes dormant",
    # after the /reports dashboard replaced the card grid with native
    # drill-down chips (reports/CHANGELOG.md, "ux(dashboard)"). The
    # payments card is hardcoded by the dashboard instead, which is
    # allowed because `payments` is in reports' manifest.depends.
    # New contributions target `reports.dashboard.widgets`.
    "reports.categories": "deprecated in reports/CLAUDE.md; successor is reports.dashboard.widgets",
}

_REGISTER = re.compile(r"""registerSlot\(\s*['"]([^'"]+)['"]""")


def _consumer_pattern(name: str) -> re.Pattern[str]:
    """Matches a host that resolves or renders ``name``.

    Both call styles appear in the tree, and the resolver is routinely
    called with an explicit context type —
    ``resolve<DiagnosisSubtabCtx>('patient.diagnosis.subtabs', …)`` in
    ``DiagnosisModeContainer.vue`` — so the generic parameter has to be
    optional here. Matching only ``resolve('…'`` reported that slot as an
    orphan while it renders fine.
    """

    quoted = rf"""['"]{re.escape(name)}['"]"""
    return re.compile(
        rf"""(?:\b(?:resolve|resolveSlot)\s*(?:<[^<>()]*>)?\s*\(\s*{quoted}"""
        rf"""|:?name=["']\s*'?{re.escape(name)}'?\s*["'])"""
    )


def _frontend_sources() -> list[tuple[str, str]]:
    """``(repo-relative path, text)`` for the host layer and every module layer."""
    roots = [REPO_ROOT / "frontend" / "app"]
    roots += sorted((REPO_ROOT / "backend" / "app" / "modules").glob("*/frontend"))

    out: list[tuple[str, str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".vue", ".ts") or "node_modules" in path.parts:
                continue
            out.append(
                (
                    str(path.relative_to(REPO_ROOT)),
                    path.read_text(encoding="utf-8", errors="replace"),
                )
            )
    return out


def _registrations(sources: list[tuple[str, str]]) -> dict[str, list[str]]:
    """``{slot name: ["path:line", …]}``."""
    found: dict[str, list[str]] = {}
    for rel, text in sources:
        for match in _REGISTER.finditer(text):
            line = text[: match.start()].count("\n") + 1
            found.setdefault(match.group(1), []).append(f"{rel}:{line}")
    return found


def _has_consumer(name: str, sources: list[tuple[str, str]]) -> bool:
    pattern = _consumer_pattern(name)
    return any(pattern.search(text) for _, text in sources)


def test_every_registered_slot_is_rendered_somewhere() -> None:
    sources = _frontend_sources()
    # Sanity-check the scan before trusting a negative result: an empty
    # or tiny corpus would make every slot look fine (or every slot look
    # orphaned), which is the false result this guard exists to avoid.
    assert len(sources) > 100, f"frontend scan looks wrong: {len(sources)} files"

    registrations = _registrations(sources)
    assert len(registrations) > 20, f"found only {len(registrations)} registered slots"

    orphans = {
        name: where
        for name, where in sorted(registrations.items())
        if name not in DORMANT_SLOTS and not _has_consumer(name, sources)
    }
    assert not orphans, "\n".join(
        [
            "these slots are registered but nothing renders them, so the entries never mount:",
            *(
                f"  {name!r} registered at {', '.join(where[:3])}"
                for name, where in orphans.items()
            ),
            "",
            "Either render the slot in the host page, fix the spelling, or "
            "add it to DORMANT_SLOTS with the reason and where that decision "
            "is documented.",
        ]
    )


def test_dormant_entries_are_still_registered() -> None:
    """Drain the allowlist when a dormant slot's last consumer goes away.

    Without this, a stale entry keeps covering for a name nobody uses and
    the next typo could be waved through by a line that no longer applies
    to anything.
    """

    registrations = _registrations(_frontend_sources())
    stale = sorted(name for name in DORMANT_SLOTS if name not in registrations)
    assert not stale, (
        f"DORMANT_SLOTS lists slots nothing registers any more: {stale} — delete those entries"
    )


def test_dormant_entries_carry_a_reason() -> None:
    for name, reason in DORMANT_SLOTS.items():
        assert len(reason) > 20, f"{name!r} needs a real reason, got {reason!r}"
