---
module: whatsapp_webhook
last_verified_commit: 0000000
---

# whatsapp_webhook — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `whatsapp_webhook.settings.read` | View webhook config | `GET /api/v1/whatsapp_webhook/settings` |
| `whatsapp_webhook.settings.write` | Edit config, rotate secret, test | `PUT /api/v1/whatsapp_webhook/settings`, `POST /api/v1/whatsapp_webhook/test` |

`manifest.role_permissions` grants `*` to **admin** only.
