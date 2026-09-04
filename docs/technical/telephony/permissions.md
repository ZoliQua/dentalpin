---
module: telephony
last_verified_commit: 0000000
---

# telephony — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `telephony.settings.read` | View gateway config | `GET /api/v1/telephony/settings` |
| `telephony.settings.write` | Edit config, rotate secret | `PUT /api/v1/telephony/settings` |
| `telephony.calls.read` | Call log, live view, pop poll | `GET /api/v1/telephony/calls`, `GET /api/v1/telephony/calls/active`, `GET /api/v1/telephony/status` |
| `telephony.calls.write` | Annotate a call | `PUT /api/v1/telephony/calls/{id}/note` |

`POST /api/v1/telephony/events/{clinic_id}` is public — authenticated by
the per-clinic HMAC signature, not RBAC.

Role grants (`manifest.role_permissions`): admin `*`; receptionist
`calls.read` + `calls.write`; dentist and assistant `calls.read`.
