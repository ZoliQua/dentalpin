"""Agent-tool parameter types must carry their format (#677).

A tool's parameter model is two things at once: the JSON schema the LLM is
shown, and the validation step ``tool_registry.call`` runs before the handler.
Typing an id as ``str`` loses both — the schema drops ``format: uuid``, so the
model has only prose telling it the shape, and the chokepoint has nothing to
reject, so a bad value fails deep in the handler with ``badly formed
hexadecimal UUID string``: a message that names no field. A ``UUID`` field
fails at the chokepoint instead, naming the parameter the model got wrong.

These tests walk every registered tool rather than a restated list, so a new
module is covered the moment it declares one.
"""

from __future__ import annotations

import datetime
import uuid
from types import UnionType
from typing import Annotated, Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from app.core.agents.tools import tool_registry
from app.core.plugins.loader import module_registry, register_discovered

# Fields whose name ends in ``_id`` but which are genuinely strings. Keep this
# list short and annotated — every entry is a claim that the value is not a
# row id. ``national_id`` is a DNI/NIE/passport number typed by a human.
NON_UUID_ID_FIELDS: frozenset[str] = frozenset(
    {
        "national_id",
    }
)

DATE_FIELD_SUFFIXES = ("_date", "_at")
DATE_FIELD_NAMES = frozenset({"date_from", "date_to"})


def _registered_tools() -> list[tuple[str, type[BaseModel]]]:
    """Every discovered module's tools, namespaced, with their parameter model.

    Discovery is used rather than the installed set: a module that is not
    installed in this environment still ships tools, and its parameter types
    are just as much part of the agent contract.
    """
    register_discovered()
    tool_registry.clear()
    for module in module_registry.list_discovered():
        tool_registry.register_from(module)
    return [(q, tool_registry.get(q).parameters) for q in tool_registry.list()]


def _base_types(annotation) -> list[type]:
    """Concrete types inside an annotation, unwrapping Annotated/Optional/list."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        out: list[type] = []
        for arg in get_args(annotation):
            if arg is not type(None):
                out += _base_types(arg)
        return out
    if origin in (list, set, tuple, frozenset):
        inner = get_args(annotation)
        return _base_types(inner[0]) if inner else []
    return [annotation]


def test_tool_id_parameters_are_uuid_typed() -> None:
    offenders = []
    checked = 0
    for qualified, model in _registered_tools():
        for name, field in model.model_fields.items():
            if not (name.endswith("_id") or name.endswith("_ids")):
                continue
            if name in NON_UUID_ID_FIELDS:
                continue
            checked += 1
            if uuid.UUID not in _base_types(field.annotation):
                offenders.append(f"{qualified}.{name}: {field.annotation}")

    # Floor: if discovery or registration silently returns nothing, an empty
    # offender list would otherwise read as a pass.
    assert checked > 50, f"only {checked} id params inspected — registration broke"
    assert not offenders, "id parameters typed as something other than UUID:\n" + "\n".join(
        sorted(offenders)
    )


def test_tool_date_parameters_are_date_typed() -> None:
    offenders = []
    checked = 0
    for qualified, model in _registered_tools():
        for name, field in model.model_fields.items():
            if not (name.endswith(DATE_FIELD_SUFFIXES) or name in DATE_FIELD_NAMES):
                continue
            checked += 1
            types = _base_types(field.annotation)
            if not any(t in types for t in (datetime.date, datetime.datetime)):
                offenders.append(f"{qualified}.{name}: {field.annotation}")

    assert checked > 10, f"only {checked} date params inspected — registration broke"
    assert not offenders, (
        "date parameters typed as something other than date/datetime:\n"
        + "\n".join(sorted(offenders))
    )


@pytest.mark.parametrize(
    "qualified,field",
    [
        ("suppliers.get_supplier", "supplier_id"),
        ("purchase_orders.create_purchase_order", "supplier_id"),
        ("inventory.adjust_inventory_stock", "item_id"),
        ("gdpr.record_gdpr_consent", "patient_id"),
    ],
)
def test_id_parameters_advertise_uuid_format(qualified: str, field: str) -> None:
    """The schema the model is given must say ``format: uuid``, not just prose.

    This is the half a type annotation buys that validation does not: it is
    what makes the model pass an id in the first place.
    """
    _registered_tools()
    schema = tool_registry.get(qualified).parameters.model_json_schema()
    prop = schema["properties"][field]
    # Optional fields render as anyOf[{...}, {"type": "null"}].
    variants = prop.get("anyOf", [prop])
    assert any(v.get("format") == "uuid" for v in variants), prop


def test_list_id_parameters_advertise_uuid_format_on_items() -> None:
    """A list of ids must carry the format on its items, not only its name."""
    _registered_tools()
    schema = tool_registry.get(
        "purchase_orders.create_purchase_order"
    ).parameters.model_json_schema()
    assert schema["properties"]["line_item_ids"]["items"]["format"] == "uuid"
