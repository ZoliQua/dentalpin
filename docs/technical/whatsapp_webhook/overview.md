---
module: whatsapp_webhook
last_verified_commit: 0000000
---

# whatsapp_webhook — overview

WhatsApp delivery for the notifications gateway via a **clinic-configured
signed webhook** (Zapier / Make / n8n). Community module,
installable/removable. Issue #63 — the zero-onboarding adapter from the
original design table.

## What it is

The thin "wire" under the channel-adapter architecture (ADR 0016):

- **`WebhookWhatsappAdapter`** registers into
  `notifications.channels.channel_registry` on activate and delivers the
  `whatsapp` channel by POSTing the rendered message as JSON to the
  clinic's hook URL, signed with the Stripe-style `X-DentalPin-Signature`
  header (shared core util `app.core.webhooks`). Unregisters on uninstall.
- **Settings**: hook URL (SSRF-guarded, https-only), show-once signing
  secret with rotation, active toggle, test delivery.

All communications logic (channel resolution, consent, outbox, retries)
lives in `notifications`. There is no inbound endpoint — the hook is
fire-and-forget; the clinic's automation owns everything past the POST.

## Coexistence

Can be installed alongside `whatsapp_kapso`; the gateway picks the adapter
whose `supports()` says the clinic configured it.

## Wire contract

See the payload documented in the module `CLAUDE.md` — the JSON keys are a
public contract for Zaps built on them.
