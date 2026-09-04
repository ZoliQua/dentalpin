---
module: documents
---

# documents — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints / tools |
|---|---|---|
| `documents.read` | List, view, download | `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/download` |
| `documents.write` | Create, edit, delete (archive), generate PDF | `POST /api/v1/documents`, `PATCH /api/v1/documents/{id}`, `DELETE /api/v1/documents/{id}`, `POST /api/v1/documents/generate`, agent tool `generate_document` |
| `admin.clinic.read` | View letterhead overrides | `GET /api/v1/documents/settings/letterhead` |
| `admin.clinic.write` | Persist letterhead overrides | `PUT /api/v1/documents/settings/letterhead` |

> The letterhead settings endpoints reuse the core
> `admin.clinic.*` clinic-profile permissions (same gate as the
> budget settings endpoints) — clinic branding is a clinic-profile
> concern, not a per-document one.

Default role mapping:

- **admin**: full management (documents are admin territory).
- **dentist**: read + write — prescribers generate prescriptions,
  certificates, referrals and radiology requests.
- **assistant**: read-only — can view documents for reference but
  cannot create or generate.
- other roles: none out of the box. Clinics can widen from the
  module admin UI.
