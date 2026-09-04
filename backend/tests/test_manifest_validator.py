"""Tests for the ecosystem-level manifest validator.

Runs as a regular pytest module so CI catches any drift in the 9
official modules: a broken manifest, an unknown role, a permission
grant that references a non-existent module permission, etc.
"""

from __future__ import annotations

from configparser import ConfigParser

from fastapi import APIRouter

from app.core.plugins.alembic_paths import alembic_cfg_path
from app.core.plugins.base import BaseModule
from app.core.plugins.loader import discover_modules
from app.core.plugins.manifest_validator import (
    validate_module,
    validate_modules,
)

# --- Live modules ---------------------------------------------------------


def test_every_shipped_module_passes_validation() -> None:
    modules = discover_modules()
    issues = validate_modules(modules)
    assert issues == [], "\n".join(f"{i.code}: {i.module_name}: {i.message}" for i in issues)


def test_every_module_migrations_dir_is_registered_in_alembic_ini() -> None:
    """M1 guard: every module migrations dir must be in the static version_locations.

    The Alembic CLI resolves ``heads``/``history``/``upgrade`` from the
    *static* ``version_locations`` in ``backend/alembic.ini``; env.py's
    runtime discovery override is too late for graph building. A module
    that ships ``migrations/versions/`` but is missing here breaks its own
    ``alembic_roundtrip`` test ("X tables missing after upgrade heads")
    even though the SQLAlchemy ``create_all`` suite passes.
    """
    config = ConfigParser()
    cfg_path = alembic_cfg_path()
    assert cfg_path.is_file(), f"missing {cfg_path}"
    config.read(cfg_path)

    registered = {
        loc.strip() for loc in config.get("alembic", "version_locations").split(":") if loc.strip()
    }

    modules_root = cfg_path.parent / "app" / "modules"
    missing: list[str] = []
    for module_dir in sorted(modules_root.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue
        versions = module_dir / "migrations" / "versions"
        if not versions.is_dir():
            continue
        expected = f"app/modules/{module_dir.name}/migrations/versions"
        if expected not in registered:
            missing.append(expected)

    assert missing == [], (
        "Modules with migrations not registered in [alembic] version_locations "
        f"of {cfg_path.name}: {missing}. Append "
        "':app/modules/<name>/migrations/versions' to the version_locations line."
    )


# --- Negative cases via stub modules --------------------------------------


class _StubModule(BaseModule):
    manifest_override: dict | None = None
    permissions_override: list[str] = []

    @classmethod
    def build(cls, **overrides) -> BaseModule:
        inst = cls()
        inst.manifest_override = overrides.pop("manifest", None)
        inst.permissions_override = overrides.pop("permissions", [])
        return inst

    @property
    def manifest(self) -> dict:  # type: ignore[override]
        return self.manifest_override or {"name": "stub", "version": "1.0.0"}

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_permissions(self) -> list[str]:
        return self.permissions_override

    def get_tools(self) -> list:
        return []


def test_rejects_invalid_version_format() -> None:
    mod = _StubModule.build(
        manifest={"name": "stub", "version": "1.0", "depends": []},
        permissions=[],
    )
    issues = validate_module(mod)
    assert any(i.code == "VERSION_FORMAT" for i in issues)


def test_rejects_unknown_role() -> None:
    mod = _StubModule.build(
        manifest={
            "name": "stub",
            "version": "1.0.0",
            "role_permissions": {"god_emperor": ["*"]},
        },
        permissions=[],
    )
    issues = validate_module(mod)
    assert any(i.code == "UNKNOWN_ROLE" for i in issues)


def test_rejects_unknown_permission_grant() -> None:
    mod = _StubModule.build(
        manifest={
            "name": "stub",
            "version": "1.0.0",
            "role_permissions": {"dentist": ["imaginary"]},
        },
        permissions=["read"],
    )
    issues = validate_module(mod)
    assert any(i.code == "UNKNOWN_PERMISSION" for i in issues)


def test_accepts_wildcard_subtree_when_declared() -> None:
    mod = _StubModule.build(
        manifest={
            "name": "stub",
            "version": "1.0.0",
            "role_permissions": {"dentist": ["plans.*"]},
        },
        permissions=["plans.read", "plans.write"],
    )
    assert validate_module(mod) == []


def test_rejects_non_namespaced_nav_permission() -> None:
    mod = _StubModule.build(
        manifest={
            "name": "stub",
            "version": "1.0.0",
            "frontend": {"navigation": [{"label": "x", "to": "/x", "permission": "bare"}]},
        },
        permissions=["bare"],
    )
    issues = validate_module(mod)
    assert any(i.code == "NAV_PERM_NOT_NAMESPACED" for i in issues)


def test_flags_unknown_dependency_when_known_set_given() -> None:
    mod = _StubModule.build(
        manifest={
            "name": "stub",
            "version": "1.0.0",
            "depends": ["ghost"],
        },
        permissions=[],
    )
    issues = validate_module(mod, known_module_names={"stub"})
    assert any(i.code == "UNKNOWN_DEPENDENCY" for i in issues)
