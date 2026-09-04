"""Every filesystem module must have a pyproject entry point (issue #324).

Production runs with ``DENTALPIN_DEV_MODULE_SCAN=False`` and relies on
``[project.entry-points."dentalpin.modules"]`` alone. Five modules —
including the non-removable ``payments`` and ``clinical_notes`` — existed
only via the dev filesystem scan and silently vanished in that mode.

This compares the *source* pyproject.toml against the modules directory
(not ``importlib.metadata``, which reads the installed dist and goes
stale until a reinstall), and verifies each declared target resolves to
a real BaseModule subclass.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import app.modules as _modules_pkg
from app.core.plugins import BaseModule

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODULES_ROOT = Path(_modules_pkg.__file__).resolve().parent


def _entry_points() -> dict[str, str]:
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["entry-points"]["dentalpin.modules"]


def _filesystem_modules() -> set[str]:
    return {
        p.name
        for p in MODULES_ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").exists() and not p.name.startswith("_")
    }


def test_every_filesystem_module_has_an_entry_point() -> None:
    declared = set(_entry_points())
    on_disk = _filesystem_modules()

    missing = on_disk - declared
    stale = declared - on_disk
    problems = []
    if missing:
        problems.append(
            f"modules with no pyproject entry point (they vanish when "
            f"DENTALPIN_DEV_MODULE_SCAN=False): {sorted(missing)}"
        )
    if stale:
        problems.append(f"entry points with no module directory behind them: {sorted(stale)}")
    assert not problems, "; ".join(problems)


def test_entry_point_targets_resolve_to_module_classes() -> None:
    bad = []
    for name, target in _entry_points().items():
        module_path, _, attr = target.partition(":")
        try:
            cls = getattr(importlib.import_module(module_path), attr)
        except (ImportError, AttributeError) as exc:
            bad.append(f"{name} -> {target}: {exc}")
            continue
        if not (isinstance(cls, type) and issubclass(cls, BaseModule)):
            bad.append(f"{name} -> {target}: not a BaseModule subclass")
        elif cls.manifest["name"] != name:
            bad.append(f"{name} -> {target}: manifest name is {cls.manifest['name']!r}")
    assert not bad, "; ".join(bad)
