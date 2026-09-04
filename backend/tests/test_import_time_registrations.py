"""ADR 0020 guard: no cross-module registration at import time (issue #325).

Discovery imports every module package on disk (installed or not), so a
registration executed at module import goes live for an uninstalled
module. The rule is "installed ⇒ live": in-memory registrations belong
in ``on_activate()``, which the loader calls only for installed modules.

The old guard grepped for two hardcoded registry names and missed four
violations. This one walks the AST of every ``app/modules/*/__init__.py``
and flags ANY top-level call whose callee looks like a registration —
``something.register(...)``, ``something.register_x(...)``, or a bare
``register*/…_register*()`` helper — regardless of which registry it
targets. ``manifest`` literals, class definitions and imports are fine;
executing registration side effects at module scope is not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.modules as _modules_pkg

MODULES_ROOT = Path(_modules_pkg.__file__).resolve().parent


def _call_name(call: ast.Call) -> str | None:
    fn = call.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return None


def _looks_like_registration(name: str) -> bool:
    lowered = name.lower()
    return lowered == "register" or lowered.startswith("register_") or "_register" in lowered


def _top_level_registration_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in tree.body:  # module top level only — function/method bodies are fine
        for call in ast.walk(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                break  # definitions don't execute their bodies at import
            if isinstance(call, ast.Call):
                name = _call_name(call)
                if name and _looks_like_registration(name):
                    hits.append(f"{path.parent.name}/__init__.py:{call.lineno} calls {name}()")
    return hits


def test_no_import_time_registrations() -> None:
    violations: list[str] = []
    for module_dir in sorted(MODULES_ROOT.iterdir()):
        init = module_dir / "__init__.py"
        if not module_dir.is_dir() or not init.exists():
            continue
        violations.extend(_top_level_registration_calls(init))

    assert not violations, (
        "Import-time registrations violate ADR 0020 — move them to the module's "
        "on_activate() so they only go live while the module is installed:\n  "
        + "\n  ".join(violations)
    )
