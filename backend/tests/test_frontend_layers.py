"""Tests for the frontend_layers helper + fixture community module."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.plugins.base import BaseModule
from app.core.plugins.frontend_layers import (
    MODULES_JSON_SCHEMA_VERSION,
    LayerEntry,
    build_payload,
    collect_layers,
    read_modules_json,
    resolve_layer_path,
    write_modules_json,
)
from tests.fixtures.sample_module import SampleModule


class _HeadlessModule(BaseModule):
    """Minimal module with no frontend layer, for negative-path tests."""

    manifest = {
        "name": "headless_fixture",
        "version": "0.0.1",
        "summary": "Backend-only fixture.",
        "author": "DentalPin tests",
        "license": "MIT",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
    }

    def get_models(self) -> list:
        return []

    def get_router(self):
        from fastapi import APIRouter

        return APIRouter()

    def get_permissions(self) -> list[str]:
        return []

    def get_tools(self) -> list:
        return []


def test_resolve_layer_path_for_fixture() -> None:
    module = SampleModule()
    path = resolve_layer_path(module)
    assert path is not None
    assert path.name == "frontend"
    assert (path / "nuxt.config.ts").exists()


def test_resolve_layer_path_returns_none_for_module_without_layer() -> None:
    # Modules that don't declare ``manifest.frontend.layer_path`` must
    # silently drop out of layer discovery.
    assert resolve_layer_path(_HeadlessModule()) is None


def test_collect_layers_filters_modules_without_layer() -> None:
    layers = collect_layers([_HeadlessModule(), SampleModule()])
    assert len(layers) == 1
    assert layers[0].module_name == "sample_community"


def test_build_payload_shape() -> None:
    entries = [LayerEntry(module_name="foo", path="/abs/foo/frontend")]
    payload = build_payload(entries)
    assert payload["version"] == MODULES_JSON_SCHEMA_VERSION
    assert payload["layers"] == ["/abs/foo/frontend"]
    assert payload["modules"] == [{"name": "foo", "path": "/abs/foo/frontend", "routes": []}]


def test_layer_routes_mirror_the_frontend_generator(tmp_path: Path) -> None:
    """#326: same traversal as scripts/modules-json.mjs — sorted walk,
    index.vue → parent path, [param] → :param."""
    from app.core.plugins.frontend_layers import _layer_routes

    pages = tmp_path / "pages"
    (pages / "widgets" / "[id]").mkdir(parents=True)
    (pages / "widgets" / "index.vue").write_text("")
    (pages / "widgets" / "[id]" / "edit.vue").write_text("")
    (pages / "widgets" / "[id]" / "index.vue").write_text("")
    (pages / "about.vue").write_text("")
    assert list(_layer_routes(tmp_path)) == [
        "/about",
        "/widgets/:id/edit",
        "/widgets/:id",
        "/widgets",
    ]


def test_write_modules_json_is_atomic_and_idempotent(tmp_path: Path) -> None:
    entries = [LayerEntry(module_name="sample", path=str(tmp_path / "layer"))]
    target = write_modules_json(entries, frontend_root=tmp_path)
    assert target == tmp_path / "modules.json"

    payload = json.loads(target.read_text())
    assert payload["layers"] == [str(tmp_path / "layer")]
    assert (tmp_path / "modules.json.tmp").exists() is False

    # Second write with no entries rewrites atomically.
    write_modules_json([], frontend_root=tmp_path)
    payload = json.loads(target.read_text())
    assert payload["layers"] == []


def test_read_modules_json_missing_file_returns_empty(tmp_path: Path) -> None:
    payload = read_modules_json(frontend_root=tmp_path)
    assert payload["layers"] == []
    assert payload["version"] == MODULES_JSON_SCHEMA_VERSION


def test_read_modules_json_tolerates_malformed(tmp_path: Path) -> None:
    (tmp_path / "modules.json").write_text("not json {")
    payload = read_modules_json(frontend_root=tmp_path)
    assert payload["layers"] == []


def test_build_payload_is_deterministic_and_sorted() -> None:
    """Install order must never leak into layer precedence (#264)."""
    scrambled = [
        LayerEntry(module_name="zeta", path="/module_layers/zeta/frontend"),
        LayerEntry(module_name="alpha", path="/module_layers/alpha/frontend"),
        LayerEntry(module_name="mid", path="/module_layers/mid/frontend"),
    ]
    payload = build_payload(scrambled)
    assert payload["layers"] == [
        "/module_layers/alpha/frontend",
        "/module_layers/mid/frontend",
        "/module_layers/zeta/frontend",
    ]
    assert payload == build_payload(list(reversed(scrambled)))
