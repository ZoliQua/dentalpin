"""Session cookies (ADR 0023, issue #353).

The backend sets the tokens as ``HttpOnly; Secure; SameSite=Lax`` cookies
so JS never sees them. A third, JS-readable ``dp_csrf`` cookie is the
double-submit token: cookie-authenticated unsafe requests must echo it in
``X-CSRF-Token`` (``dependencies.get_auth_token``); it is minted per
refresh-token family and survives rotation, so an already-mounted tab
keeps a valid token after another tab refreshed.

All three share ``path=/`` so a server-rendered page request carries the
refresh cookie too and SSR can refresh an expired access cookie in place
(a path-scoped refresh cookie never reached Nuxt, so every reload after
expiry bounced through ``/login``). ``COOKIE_DOMAIN`` widens them to a
parent domain for split-host deployments.
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlsplit

from fastapi import Request, Response

from app.config import settings

logger = logging.getLogger(__name__)

ACCESS_COOKIE = "dp_access"
REFRESH_COOKIE = "dp_refresh"
CSRF_COOKIE = "dp_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _secure() -> bool:
    # Plain http://localhost in dev/e2e can't carry Secure cookies.
    return settings.ENVIRONMENT == "production"


def _domain() -> str | None:
    return settings.COOKIE_DOMAIN.strip() or None


_HOST_ONLY_WARNED = False


def _shared_parent(app_host: str, api_host: str) -> str | None:
    """Longest common dotted suffix of two hosts, at least two labels:
    ``demo.example.com`` + ``api-demo.example.com`` -> ``.example.com``."""
    common: list[str] = []
    for left, right in zip(reversed(app_host.split(".")), reversed(api_host.split("."))):
        if left != right:
            break
        common.append(left)
    if len(common) < 2:
        return None
    return "." + ".".join(reversed(common))


def warn_if_host_only(request: Request | None) -> None:
    """Warn once when the session cookies can never reach the app (#444).

    A cookie without ``Domain`` is host-only. When the app is served from
    another host than the API, the browser keeps the session cookies for
    the API host: client-side calls still work, but a server-rendered page
    load carries no cookie at all, so every reload lands on ``/login``.
    Nothing fails loudly at deploy time, so say it here, once, with the
    value to set.
    """
    global _HOST_ONLY_WARNED
    if _HOST_ONLY_WARNED or _domain() or request is None:
        return
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    app_host = (urlsplit(origin).hostname or "").lower()
    api_host = (request.headers.get("host") or request.url.hostname or "").split(":")[0].lower()
    if not app_host or not api_host or app_host == api_host:
        return
    _HOST_ONLY_WARNED = True
    parent = _shared_parent(app_host, api_host)
    fix = (
        f"set COOKIE_DOMAIN={parent} and restart"
        if parent
        else "serve both from sibling hosts of one parent domain and set COOKIE_DOMAIN"
    )
    logger.warning(
        "Session cookies are host-only: the app (%s) and the API (%s) are different hosts "
        "and COOKIE_DOMAIN is empty, so the browser never sends dp_access/dp_refresh to the "
        "app and every page reload will redirect to /login - %s.",
        app_host,
        api_host,
        fix,
    )


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    request: Request | None = None,
) -> None:
    warn_if_host_only(request)
    access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_ttl,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
        domain=_domain(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_ttl,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
        domain=_domain(),
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_ttl,
        httponly=False,  # the double-submit half JS must read
        secure=_secure(),
        samesite="lax",
        path="/",
        domain=_domain(),
    )


def clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", domain=_domain())
