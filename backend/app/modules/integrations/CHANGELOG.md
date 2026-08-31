# Changelog — integrations module

## Unreleased

- feat(#65): the three flagged Phase-1 follow-ups — (1) **public read API** under `/api/v1/integrations/public/` consuming the `dp_` bearer tokens with per-scope authorization (`/ping` introspection for Zapier auth tests, patient search by phone/email/NIF/name + read, curated response shape, rate-limited); (2) **stable `event_id`** generated once per event and shared across every subscriber's delivery (payload top-level field; `int_0003` column, legacy rows fall back to the delivery id); (3) **trigger catalog expanded** to 6 events (`appointment.scheduled`/`.cancelled`, `budget.accepted`, `invoice.sent` join the original two), each with a frozen sample payload served by `GET /webhooks/triggers` and pinned by test.

- Initial module (Phase 1 of issue #65): webhook subscription CRUD,
  outbox-backed delivery with retry/backoff/auto-disable, Stripe-style
  HMAC-SHA256 signing, and one working trigger (`patient.created`).
- Added second Phase 1 trigger `appointment.completed`, sharing an
  `_enqueue` helper with `on_patient_created` (identical apart from
  the `EventType`).
- Added `ApiToken` model + admin CRUD (`GET/POST /tokens`, `POST
  /tokens/{id}/revoke`). Plaintext is `dp_` + `secrets.token_urlsafe(32)`
  (recognizable prefix for secret-scanning tools), shown once,
  SHA-256-hashed at rest (not Fernet/bcrypt — see `models.ApiToken`
  docstring). `scopes` validated against a closed catalog
  (`SUPPORTED_TOKEN_SCOPES`), not free text. No consumer endpoint
  yet — the public data-read API is a follow-up PR.
- Added `occurred_at` to every enqueued webhook payload.
- SSRF guard on `target_url` (`url_safety.py`) — not in the original
  issue scoping. Validated at subscription create/update (async, via
  the event loop's own resolver — not a Pydantic validator, which
  can't `await`) and again immediately before every dispatch (a
  hostname can be repointed after creation; this narrows the window
  rather than fully defending against DNS rebinding, since httpx
  re-resolves on connect). Rejects non-`https` schemes and any
  hostname/literal that resolves to a private, loopback, link-local,
  reserved, or multicast address, including the cloud metadata IP.
  `client.py` also sets `follow_redirects=False` so a validated
  request can't be redirected to an unvalidated internal URL.
- Signing header renamed `X-Integrations-Signature` →
  `X-DentalPin-Signature` (a public contract, so committing to the
  product name rather than the internal module name).
- Fixed `update_subscription`: `description` can now actually be
  cleared to `null` (was previously unclearable).
- `get_tools()` added, returning `[]` (new-module checklist).
- `manifest.depends` stays `["patients"]` — `agenda` (the
  `appointment.completed` publisher) is not a dependency, since
  consuming an event doesn't require depending on its publisher.
- Added `CLAUDE.md` and this file.
- Added the round-trip uninstall test required for `removable=True`
  modules (`test_uninstall_roundtrip.py`, `alembic_roundtrip` marker).
