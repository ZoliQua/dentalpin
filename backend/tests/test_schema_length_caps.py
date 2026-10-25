"""A write schema never accepts a string its own column cannot store.

``VARCHAR(n)`` rejects a longer value on INSERT —
``StringDataRightTruncationError: value too long for type character
varying(50)`` — and nothing maps a database error to a status code
(``app/main.py`` has handlers for ``HTTPException`` and bare
``Exception``, nothing in between), so the clinic gets a 500 and the log
gets a traceback. A ``max_length`` on the schema turns the same input
into the 422 it always was.

That was the state of 17 fields across 8 modules: an invoice line's
``internal_code`` (50) and ``vat_exempt_reason`` (200), an invoice
series' ``description`` (200), a signature's ``signed_by_email`` (255), a
catalog category's ``icon`` (50), the copilot ``model`` (100) — all
unbounded at the boundary.

The check pairs each write schema with **one** model by name
(``InvoiceItemCreate`` -> ``InvoiceItem``), never by field name alone:
``description`` exists on ``InvoiceItem`` (500) and ``InvoiceSeries``
(200), and comparing against the wrong one is how a sweep invents a
defect that is not there.

Out of scope by design: a field whose vocabulary is validated elsewhere
is still checked here, because a cap is right either way — being a
closed vocabulary is a separate problem (see the ``Literal``-typing
work in #679), and a 20-character cap on a status is not the fix for it.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
import typing

from pydantic import BaseModel
from sqlalchemy import String

import app.modules as modules_pkg

# Schemas that write: the suffixes the tree actually uses.
WRITE_SUFFIX = re.compile(r"(Create|Update|Upsert|Patch|Input|Submission|Request|Payload|Write)$")


def _string_columns(models_module) -> dict[str, dict[str, int]]:
    """``{model name: {column: length}}`` for length-capped string columns."""
    out: dict[str, dict[str, int]] = {}
    for _, obj in inspect.getmembers(models_module, inspect.isclass):
        table = getattr(obj, "__table__", None)
        if table is None or obj.__module__ != models_module.__name__:
            continue
        out[obj.__name__] = {
            col.name: col.type.length
            for col in table.columns
            if isinstance(col.type, String) and col.type.length
        }
    return out


def _is_plain_str(annotation: object) -> bool:
    """``str`` or ``str | None``, but not a ``Literal`` (already bounded)."""
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) is typing.Literal:
        return False
    if args:
        if any(typing.get_origin(arg) is typing.Literal for arg in args):
            return False
        return any(arg is str for arg in args)
    return annotation is str


def _cap(field) -> int | None:
    caps = [getattr(meta, "max_length", None) for meta in field.metadata]
    found = [cap for cap in caps if cap]
    return max(found) if found else None


def _has_pattern(field) -> bool:
    return any(getattr(meta, "pattern", None) for meta in field.metadata)


def test_write_schemas_cap_strings_at_the_column_length() -> None:
    offenders: list[str] = []
    pairs_checked = 0

    for name in sorted(mod.name for mod in pkgutil.iter_modules(modules_pkg.__path__)):
        try:
            models_module = importlib.import_module(f"app.modules.{name}.models")
            schemas_module = importlib.import_module(f"app.modules.{name}.schemas")
        except ModuleNotFoundError:
            continue

        columns = _string_columns(models_module)
        source = inspect.getsource(schemas_module)

        for schema_name, schema in inspect.getmembers(schemas_module, inspect.isclass):
            if not (issubclass(schema, BaseModel) and schema is not BaseModel):
                continue
            if schema.__module__ != schemas_module.__name__ or not WRITE_SUFFIX.search(schema_name):
                continue

            stem = WRITE_SUFFIX.sub("", schema_name)
            candidates = [
                model
                for model in columns
                if model == stem or model.endswith(stem) or stem.endswith(model)
            ]
            if len(candidates) != 1:
                # Cannot say which table this schema writes — a guess here
                # is how a field-name match reports a phantom defect.
                continue
            model = candidates[0]

            for field_name, field in schema.model_fields.items():
                length = columns[model].get(field_name)
                if length is None or not _is_plain_str(field.annotation):
                    continue
                # A field_validator is validation this scan cannot read.
                if re.search(rf"""field_validator\(\s*['"]{field_name}['"]""", source):
                    continue
                pairs_checked += 1
                cap = _cap(field)
                if cap is None and _has_pattern(field):
                    continue  # a regex bounds the value
                if cap is not None and cap <= length:
                    continue
                offenders.append(
                    f"  {name}.{schema_name}.{field_name}: "
                    f"schema cap {cap or 'none'} > {model}.{field_name} VARCHAR({length})"
                )

    # Sanity floor: a sweep that paired nothing would pass vacuously.
    assert pairs_checked > 100, f"schema/column pairing looks wrong: {pairs_checked} fields"

    assert not offenders, "\n".join(
        [
            "these write schemas accept a string the column cannot store, so the",
            "insert raises StringDataRightTruncation and the caller gets a 500:",
            *offenders,
            "",
            "Add max_length (or a pattern) matching the column.",
        ]
    )
