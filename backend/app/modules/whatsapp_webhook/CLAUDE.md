# whatsapp_webhook module

WhatsApp delivery for the notifications gateway via a **clinic-configured
signed webhook** (Zapier / Make / n8n). The zero-onboarding path from issue
#63: no vendor account, no Meta verification — the clinic pastes a hook URL
and their automation routes each message to WhatsApp (or anywhere else).
Community, installable/removable. All comms logic (routing, consent,
outbox, retries) lives in `notifications`; this module is pure wire.

Issue #63. ADR 0016 (channel adapters).

## Public API

Routes at `/api/v1/whatsapp_webhook/`:

| Method | Path | Auth |
|---|---|---|
| GET/PUT | `/settings` | `whatsapp_webhook.settings.read` / `.write` |
| POST | `/test` | `whatsapp_webhook.settings.write` |

No inbound endpoint — the hook is fire-and-forget by design; delivery
statuses/replies would live in whatever the clinic's automation does.

## Dependencies

`manifest.depends = ["notifications"]`. The only cross-module import is
`app.modules.notifications.channels` (the adapter contract). Shared webhook
plumbing (Stripe-style signing, SSRF guard) comes from **core**
(`app.core.webhooks`) — hoisted out of `integrations` when this second
consumer appeared; optional modules never import each other.

## Channel adapter

`WebhookWhatsappAdapter` (`adapter.py`) registers into
`notifications.channels.channel_registry` from `on_activate` (ADR 0020);
`uninstall()` unregisters it. `supports()` = an active
`WhatsappWebhookSettings` row exists. `send()` POSTs the payload below and
maps the response to an `AdapterResult` (2xx ⇒ sent; the receiver's JSON
`id`, when present, becomes `provider_message_id`).

## Wire contract (documented — breaking to change)

POST body, signed with `X-DentalPin-Signature` (`t=<ts>,v1=<hmac>`, same
Stripe scheme as the integrations module; verify against the raw bytes):

```json
{
  "type": "notification.whatsapp",          // "notification.test" from /test
  "to": "+34600111222",
  "to_name": "Ana",
  "clinic_id": "…", "patient_id": "…",
  "template_key": "appointment_reminder",
  "locale": "es",
  "message_kind": "template",
  "text": "…rendered body or null…",
  "context": { "patient_name": "Ana", … },
  "occurred_at": "2026-08-31T09:00:00+00:00"
}
```

## Coexistence with whatsapp_kapso

Both register for `Channel.WHATSAPP`. The gateway resolves per clinic via
`_supporting_adapter` → `channel_registry.adapters_for_channel` — the
**configured** adapter wins (`supports()` reads the clinic's own settings
row), most-recently-registered is only the tie-break when both are
configured. Don't go back to `get_for_channel` in gateway code: it returns
one arbitrary vendor and broke the two-vendor case.

## Secrets

The signing secret is generated server-side (`whsec_` +
`token_urlsafe(32)`), Fernet-encrypted at rest (`app.core.email.encryption`),
and returned **once** — in the response to the save that (re)generated it.
Rotation via `PUT /settings {"rotate_secret": true}`.

## SSRF

`target_url` is clinic-supplied and the server POSTs to it:
`validate_new_url` at save + `validate_before_dispatch` in `client.py`
before every send (https-only, public IPs only) — same double-checkpoint
as the integrations module, same core util.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch `whatsapp_webhook` (`wwh_0001`). Round-trip uninstall
  test drops only `whatsapp_webhook_settings`.

## Gotchas

- **The payload is a public contract.** Clinics build Zaps against these
  key names; treat any change as breaking and version it.
- **Proactive-template rules still apply upstream.** The gateway decides
  template vs session; this adapter sends whatever it is handed and does
  not enforce the 24h window (the receiving automation's problem space).
- **`last_delivery_at`/`last_error` are flushed, not committed** — the
  gateway's dispatcher owns the commit for the delivery attempt.

## Related ADRs

- `docs/adr/0016-channel-adapter-architecture.md`

## CHANGELOG

See `./CHANGELOG.md`.
