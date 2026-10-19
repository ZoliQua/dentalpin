"""Every value of a closed backend vocabulary has a UI label.

The UI renders these vocabularies through a dynamic key —
``t(`payments.methods.${payment.method}`)`` — so the connection between
the Python tuple and the i18n namespace is one interpolation that no
typechecker sees. Add a member on the backend and the frontend keeps
compiling, keeps passing locale parity (the key is absent from *every*
locale, so every locale agrees), and renders the bare key, or the raw
value, to the clinic.

That is not hypothetical:

- ``checked_in`` / ``in_treatment`` joined ``APPOINTMENT_STATUSES`` with
  the waiting-room flow, and the patient file's appointment list — which
  read the flat ``appointments.<status>`` namespace, a stale duplicate of
  ``appointments.status.*`` — showed ``appointments.checked_in`` in the
  badge. Its own colour helper already handled both statuses.
- ``upi`` / ``netbanking`` joined ``PAYMENT_METHODS`` for India (#365)
  but not ``invoice.payments.methods``, so invoices and the payment-method
  report tile labelled them ``upi`` / ``netbanking`` (the helper in
  ``utils/paymentMethod.ts`` falls back to the raw value).

Both are fixed; this table is what keeps the next member honest.

**Scope.** English only, on purpose: every locale is held to the English
key set by ``frontend/tests/i18n/locale-parity.test.ts``, so a key that
exists here exists everywhere. The sibling
``frontend/tests/i18n/key-resolution.test.ts`` covers the *literal*
``t('…')`` call sites; a dynamic key is exactly what it cannot see.

**What this does not guard.** It checks the namespace each vocabulary is
*supposed* to be read from. A second, stale copy of the same vocabulary
elsewhere in the bundle is invisible here — partial overlap between
unrelated namespaces (``pending``, ``email``, ``other``…) is far too
common for a heuristic to flag. The defence against that is not having
duplicates: the appointment one was deleted rather than completed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from app.modules.agenda.models import APPOINTMENT_STATUSES
from app.modules.contacts.models import CONTACT_TYPES
from app.modules.expenses.models import EXPENSE_CATEGORIES
from app.modules.leads.models import AVAILABILITY_SLOTS, LEAD_STATUSES
from app.modules.medication_catalog.models import MEDICATION_FORMS
from app.modules.orthodontics.defaults import DEFAULT_PROCEDURES
from app.modules.orthodontics.models import APPLIANCE_TYPES, CASE_STATUSES
from app.modules.payments.models import PAYMENT_METHODS, REFUND_REASON_CODES
from app.modules.recalls.models import CHANNELS, OUTCOMES, PRIORITIES, REASONS, STATUSES
from app.modules.treatment_plan.router import PIPELINE_TABS
from app.modules.treatment_plan.service import VALID_CLOSURE_REASONS
from app.modules.verifactu.models import RECORD_STATES

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_LOCALES = REPO_ROOT / "frontend" / "i18n" / "locales"
MODULES = REPO_ROOT / "backend" / "app" / "modules"

# i18n namespace -> the vocabulary whose members it must label.
# A vocabulary may be read from more than one namespace (billing and the
# reports tile share ``invoice.payments.methods`` through
# ``utils/paymentMethod.ts``, while the payments layer has its own).
VOCABULARY_LABELS: dict[str, Iterable[str]] = {
    "appointments.status": APPOINTMENT_STATUSES,
    "contacts.types": CONTACT_TYPES,
    "expenses.categories": EXPENSE_CATEGORIES,
    "invoice.payments.methods": PAYMENT_METHODS,
    "leads.slots": AVAILABILITY_SLOTS,
    "leads.status": LEAD_STATUSES,
    "medications.forms": MEDICATION_FORMS,
    "orthodontics.appliance": APPLIANCE_TYPES,
    "orthodontics.procedures": DEFAULT_PROCEDURES,
    "orthodontics.status": CASE_STATUSES,
    "payments.methods": PAYMENT_METHODS,
    "payments.refund.reasonCodes": REFUND_REASON_CODES,
    "pipeline.tabs": PIPELINE_TABS,
    "recalls.channel": CHANNELS,
    "recalls.outcome": OUTCOMES,
    "recalls.priority": PRIORITIES,
    "recalls.reasons": REASONS,
    "recalls.status": STATUSES,
    "treatmentPlans.closureReason": VALID_CLOSURE_REASONS,
    "verifactu.recordState": RECORD_STATES,
}


def _leaves(tree: dict, prefix: str = "", out: set[str] | None = None) -> set[str]:
    """Dotted paths of every leaf string in a message tree."""
    out = set() if out is None else out
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _leaves(value, path, out)
        else:
            out.add(path)
    return out


def _english_keys() -> set[str]:
    """Host messages plus every module layer's ``en.json`` / ``<mod>-en.json``."""
    keys = _leaves(json.loads((HOST_LOCALES / "en.json").read_text(encoding="utf-8")))
    for locales in sorted(MODULES.glob("*/frontend/i18n/locales")):
        for path in sorted(locales.iterdir()):
            if path.name == "en.json" or path.name.endswith("-en.json"):
                keys |= _leaves(json.loads(path.read_text(encoding="utf-8")))
    return keys


def _frontend_sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    roots = [REPO_ROOT / "frontend" / "app"]
    roots += sorted(MODULES.glob("*/frontend"))
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


def test_every_vocabulary_member_has_a_label() -> None:
    keys = _english_keys()
    # A loader that silently read nothing would pass this table vacuously.
    assert len(keys) > 4000, f"merged English key set looks wrong: {len(keys)}"

    gaps: list[str] = []
    for prefix, vocabulary in sorted(VOCABULARY_LABELS.items()):
        members = sorted(vocabulary)
        assert len(members) >= 3, f"{prefix}: vocabulary looks wrong ({members})"
        missing = [m for m in members if f"{prefix}.{m}" not in keys]
        if missing:
            gaps.append(f"  {prefix}.<value> has no label for {missing} (vocabulary: {members})")

    assert not gaps, "\n".join(
        [
            "these backend values reach a dynamic i18n key with no message behind it,",
            "so the UI renders the key (or the raw value) to the clinic:",
            *gaps,
            "",
            "Add the label to the English file the namespace lives in; "
            "locale-parity.test.ts will then ask for the other locales.",
        ]
    )


def test_every_listed_namespace_is_read_dynamically() -> None:
    """Drain the table when a namespace stops being used with a dynamic key.

    Without this, an entry outlives the code it describes and the table
    stops meaning anything. Both call shapes count — the template literal
    the tree uses everywhere today, and string concatenation.
    """

    sources = _frontend_sources()
    assert len(sources) > 100, f"frontend scan looks wrong: {len(sources)} files"

    unused = []
    for prefix in sorted(VOCABULARY_LABELS):
        quoted = re.escape(prefix)
        pattern = re.compile(rf"""`{quoted}\.\$\{{|['"]{quoted}\.['"]\s*\+""")
        if not any(pattern.search(text) for _, text in sources):
            unused.append(prefix)

    assert not unused, (
        f"no dynamic `{{prefix}}.${{value}}` call site left for {unused} — "
        "either the namespace was renamed (update the table) or the "
        "vocabulary is no longer rendered (drop the entry)"
    )
