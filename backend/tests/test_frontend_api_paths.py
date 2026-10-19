"""Every API path the frontend calls is a route the backend mounts.

A path lives as a string on one side and a decorator on the other, with
nothing between them. Get it wrong and the request 404s at runtime —
and because the call sites wrap their fetches in ``try``/``catch`` to
stay quiet when a module is uninstalled, the symptom is not an error but
a feature that renders empty forever. Three such paths were in the tree
when this guard was written:

- ``GET /api/v1/appointments/{id}`` in treatment_plan's
  ``MarkPerformedFollowupPrompt`` — agenda mounts that detail route under
  its own prefix, so the "mark the leftover linked treatments performed"
  prompt (#207) listed nothing after every completed appointment.
- ``POST`` / ``DELETE /api/v1/clinical_notes/attachments`` — media owns
  the attachment rows and the write endpoints; clinical_notes exposes
  only the note-aware read.
- ``GET /api/v1/auth/users/{id}`` on the budgets list, which does not
  exist (the users router has PUT and DELETE for an id, no GET).

The route table is the **OpenAPI schema** of the test app
(``app.main.app``), which ``tests/conftest.py`` mounts with every
*discovered* module — "the lifespan mounts only the installed ones;
conftest is the one place that explicitly wants all".

The schema, rather than walking ``app.routes``, because the route tree is
not a flat list of ``APIRoute`` on every FastAPI version. Measured on the
two this repo sees: on 0.135 ``include_router`` flattens into
``APIRoute`` objects, and on the 0.141 that CI resolves (``pip install -e
".[dev]"`` ignores ``uv.lock``) it keeps a nested ``_IncludedRouter``
node that exposes neither ``routes`` nor ``prefix``. Two earlier versions
of this test enumerated routes directly and reported 37 healthy calls as
orphans on CI only — first because ``module.get_router()`` of the three
sub-router modules yields ``_IncludedRouter`` entries, then because
``app.routes`` yields them too (3 ``APIRoute`` against 709 locally).
``app.openapi()`` answers 515 paths / 709 method pairs on both, carries
the final prefixes, and hides nothing: no route in this app sets
``include_in_schema=False``.

The completeness floors below are what turned that CI failure into a
one-line diagnosis, and they fail loudly if conftest ever stops mounting
everything.

Deliberate limits of the scan, so a reader knows what a pass means:

- Only literal paths starting with ``/api/`` are checked. A path built
  entirely from a variable is invisible here.
- An interpolated segment (``${id}``) matches **any** one segment, path
  parameter or literal: ``medical_reference/${kind}`` legitimately
  resolves to ``/medical_reference/diseases``.
- A trailing interpolation whose expression looks like a query string
  (``${qs}``, ``${params}``, a ternary) is treated as a suffix, not a
  segment.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.plugins.loader import discover_modules
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES = REPO_ROOT / "backend" / "app" / "modules"

# Stand-in for an interpolated segment; cannot occur in a real path.
WILDCARD = "\x00"

# An interpolation that carries a query string rather than a path segment.
QUERYISH = re.compile(r"^(qs|q|params?|query|queryString|suffix|search|filters?)\b", re.I)

CALL = re.compile(
    r"""(?:api\.(?P<verb>get|post|put|patch|del|raw)\s*(?:<[^()]*?>)?\s*\("""
    r"""|(?P<fetch>\$fetch|useFetch)\s*(?:<[^()]*?>)?\s*\()"""
    r"""\s*(?P<q>['"`])(?P<path>/api/[^'"`]*)(?P=q)(?=(?P<rest>.{0,220}))""",
    re.S,
)
VERB = {"get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "del": "DELETE", "raw": "GET"}
SKIP_DIRS = {"node_modules", ".nuxt", ".output", "dist"}


HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


def _route_table() -> tuple[dict[str, list[list[str]]], dict[str, int]]:
    """``({method: [[segment, …], …]}, {module: route count})``."""
    table: dict[str, list[list[str]]] = {}
    per_module: dict[str, int] = dict.fromkeys(module.name for module in discover_modules())

    for path, operations in app.openapi()["paths"].items():
        segments = [t for t in path.strip("/").split("/") if t]
        for method in operations:
            if method.lower() not in HTTP_METHODS:
                continue
            table.setdefault(method.upper(), []).append(segments)
            # /api/v1/<module name>/… — the prefix the loader mounts under
            if len(segments) > 2 and segments[2] in per_module:
                per_module[segments[2]] = (per_module[segments[2]] or 0) + 1

    return table, {name: count or 0 for name, count in per_module.items()}


def _frontend_segments(path: str) -> list[str]:
    path = path.split("?")[0]

    def sub(match: re.Match[str]) -> str:
        return "" if QUERYISH.match(match.group(1).strip()) else WILDCARD

    path = re.sub(r"\$\{([^{}]*)\}", sub, path)
    # An interpolation we could not close (a ternary, a nested template):
    # everything from there on is unknown, so treat it as a prefix.
    cut = path.find("${")
    if cut != -1:
        path = path[:cut] + WILDCARD
    return [t for t in path.strip("/").split("/") if t]


def _matches(called: list[str], route: list[str]) -> bool:
    if len(called) != len(route):
        return False
    for mine, theirs in zip(called, route, strict=True):
        if mine == WILDCARD or theirs.startswith("{"):
            continue
        if WILDCARD in mine:  # e.g. "retry${qs}" -> "retry" + unknown tail
            if not theirs.startswith(mine.split(WILDCARD)[0]):
                return False
            continue
        if mine != theirs:
            return False
    return True


def _frontend_sources() -> list[tuple[str, str]]:
    roots = [REPO_ROOT / "frontend" / "app"]
    roots += sorted(MODULES.glob("*/frontend"))
    out: list[tuple[str, str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".vue", ".ts", ".js") or SKIP_DIRS & set(path.parts):
                continue
            out.append(
                (
                    str(path.relative_to(REPO_ROOT)),
                    path.read_text(encoding="utf-8", errors="replace"),
                )
            )
    return out


def test_every_frontend_api_call_hits_a_mounted_route() -> None:
    table, per_module = _route_table()
    sources = _frontend_sources()

    # Completeness first. A table missing one module turns every healthy
    # call into that module into an "orphan", which is a far more
    # confusing failure than the one this test is for.
    total = sum(len(v) for v in table.values())
    with_routes = sorted(name for name, count in per_module.items() if count)
    assert total > 500, f"route table looks wrong: {total} routes from {len(per_module)} modules"
    assert len(with_routes) > 50, (
        f"route table is incomplete — only these modules contributed a route: {with_routes}"
    )
    assert len(sources) > 100, f"frontend scan looks wrong: {len(sources)} files"

    unmatched: dict[tuple[str, str], list[str]] = {}
    checked = 0
    for rel, text in sources:
        for match in CALL.finditer(text):
            method = VERB.get(match.group("verb") or "", "GET")
            if match.group("fetch"):
                explicit = re.search(r"method:\s*['\"](\w+)['\"]", match.group("rest"))
                method = explicit.group(1).upper() if explicit else "GET"
            segments = _frontend_segments(match.group("path"))
            checked += 1
            if any(_matches(segments, route) for route in table.get(method, [])):
                continue
            line = text[: match.start()].count("\n") + 1
            unmatched.setdefault((method, match.group("path")), []).append(f"{rel}:{line}")

    assert checked > 300, f"literal API-call sweep looks wrong: {checked} calls"

    # Before blaming the call sites: if an unmatched path belongs to a
    # module that contributed no route at all, the table is what is
    # broken, and saying so beats a wall of healthy calls.
    empty_modules = {name for name, count in per_module.items() if not count}
    suspects = sorted(
        {
            path.split("/")[3]
            for _, path in unmatched
            if len(path.split("/")) > 3 and path.split("/")[3] in empty_modules
        }
    )
    assert not suspects, (
        f"the test app mounts no route for {suspects} — the table is "
        "incomplete, not the frontend (mounted modules: "
        f"{len(per_module) - len(empty_modules)}/{len(per_module)})"
    )

    assert not unmatched, "\n".join(
        [
            "these frontend calls name no route the backend mounts, so they 404:",
            *(
                f"  {method} {path}\n      " + "\n      ".join(sites)
                for (method, path), sites in sorted(unmatched.items())
            ),
            "",
            "Fix the path (check which module owns the endpoint — the mount "
            "prefix is /api/v1/<module name>), or add the route.",
        ]
    )
