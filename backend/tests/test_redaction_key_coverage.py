"""Every person-identifying key a tool returns must be redacted (#687).

``Redactor._redact_scalar`` matches on the **key name**, so the key sets in
``app/core/agents/redaction.py`` are a denylist: a name or an email address
under a key nobody listed reaches the cloud LLM provider verbatim. A list
that has to be extended by hand for 59 modules' tool results cannot be kept
closed by memory, so this walks the results themselves.

The walk is static (the tool handlers' returned dict literals) rather than a
live call: it needs no database, and a key is part of the contract the moment
it is written down.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.core.agents.redaction import _ID_KIND, _KIND_FOR_KEY, Redactor

MODULES_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "modules"

# Keys that end in ``_name`` but name a thing, not a person. Every entry is a
# claim that the value identifies no natural person — keep it annotated.
NON_PERSON_NAME_KEYS: frozenset[str] = frozenset(
    {
        # An inventory item ("Composite syringe A2").
        "item_name",
        # A supplier organisation. Note the edge: a sole trader's trading
        # name *is* personal data. The value-level fallback in
        # ``_redact_scalar`` covers that case once the name has been seen
        # under a covered key in the same conversation; a dedicated
        # supplier-is-a-person rule would need a model change, not a key.
        "supplier_name",
    }
)


def _returned_keys() -> dict[str, set[str]]:
    """Every string key in a dict literal inside a module's ``tools.py``."""
    keys: dict[str, set[str]] = {}
    for path in sorted(MODULES_DIR.glob("*/tools.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Dict):
                continue
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.setdefault(key.value, set()).add(path.parent.name)
    return keys


def _covered(key: str) -> bool:
    return key.lower() in _KIND_FOR_KEY


def test_contact_detail_keys_are_redacted() -> None:
    """An email address or a phone number is personal data under any key."""
    keys = _returned_keys()
    offenders = []
    checked = 0
    for key, modules in sorted(keys.items()):
        if not key.endswith(("email", "phone", "mobile", "telephone")):
            continue
        checked += 1
        if not _covered(key):
            offenders.append(f"{key} (returned by {', '.join(sorted(modules))})")

    assert checked >= 3, f"only {checked} contact keys inspected — the walk broke"
    assert not offenders, (
        "contact-detail keys that reach the LLM provider in cleartext — add "
        "them to _EMAIL_KEYS/_PHONE_KEYS in redaction.py:\n" + "\n".join(offenders)
    )


def test_name_keys_are_either_redacted_or_declared_non_personal() -> None:
    """A ``*_name`` key is a person's name until someone says otherwise."""
    keys = _returned_keys()
    unclassified = []
    checked = 0
    for key, modules in sorted(keys.items()):
        if key != "name" and not key.endswith("_name"):
            continue
        checked += 1
        if _covered(key) or key in NON_PERSON_NAME_KEYS:
            continue
        unclassified.append(f"{key} (returned by {', '.join(sorted(modules))})")

    assert checked >= 5, f"only {checked} name keys inspected — the walk broke"
    assert not unclassified, (
        "name keys that are neither redacted nor declared non-personal. Add "
        "them to _NAME_KEYS in redaction.py, or to NON_PERSON_NAME_KEYS here "
        "with the reason they identify no person:\n" + "\n".join(unclassified)
    )


def test_patient_reference_keys_are_tokenized() -> None:
    """Every key holding a patient's id must tokenize, not just ``patient_id``."""
    keys = _returned_keys()
    offenders = [
        key for key in sorted(keys) if key.endswith("patient_id") and key.lower() not in _ID_KIND
    ]
    assert not offenders, "patient references missing from _ID_KIND: " + ", ".join(offenders)


@pytest.mark.parametrize(
    "key,value",
    [
        ("professional_name", "Dr. Ana Ruiz"),
        ("created_by_name", "Luis Pérez"),
        ("recipient_email", "maria.garcia@example.com"),
        ("filename", "Garcia_Maria_2026-03-04.dcm"),
        ("suggested_patient_id", "6fd1b801-7c63-4916-8810-d494a7aa4585"),
    ],
)
def test_measured_leaks_are_closed(key: str, value: str) -> None:
    """The five keys #687 measured leaving the server in cleartext."""
    out = Redactor(enabled=True, salt="test-salt").redact_result({key: value})
    assert out[key] != value, f"{key} still leaves in cleartext"


def test_a_known_value_is_tokenized_under_an_unlisted_key() -> None:
    """The same value under two keys must not be token in one and plain in the other.

    This is the half a key list cannot cover: the table already holds the
    value because a covered key put it there.
    """
    redactor = Redactor(enabled=True, salt="test-salt")
    out = redactor.redact_result(
        {"email": "maria.garcia@example.com", "some_future_key": "maria.garcia@example.com"}
    )
    assert out["some_future_key"] == out["email"] != "maria.garcia@example.com"


def test_non_personal_values_stay_readable() -> None:
    """Redaction must not tokenize everything — the model still has to work."""
    out = Redactor(enabled=True, salt="test-salt").redact_result(
        {"status": "pending", "item_name": "Composite syringe A2", "quantity": "12"}
    )
    assert out == {"status": "pending", "item_name": "Composite syringe A2", "quantity": "12"}


def test_tokens_rehydrate_to_the_real_values() -> None:
    """A new kind must round-trip like the existing ones."""
    redactor = Redactor(enabled=True, salt="test-salt")
    out = redactor.redact_result(
        {"filename": "Garcia_Maria.dcm", "professional_name": "Dr. Ana Ruiz"}
    )
    restored = redactor.rehydrate(f"{out['filename']} / {out['professional_name']}")
    assert restored == "Garcia_Maria.dcm / Dr. Ana Ruiz"
