---
module: agenda
last_verified_commit: 27442250
---

# Agenda — permissions

Returned by `AgendaModule.get_permissions()`
(relative names; the registry namespaces them as `agenda.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `agenda.appointments.read` | View appointments and export them. | `GET /agenda/appointments`, `GET /agenda/appointments/{appointment_id}`, `GET /agenda/appointments/{appointment_id}.ics` (RFC 5545 export, #129) |
| `agenda.appointments.write` | Create and edit appointments, mint QR check-in tokens and render QR images. | Appointment CRUD and transitions, `POST /agenda/appointments/{appointment_id}/check-in-token`, `GET /agenda/appointments/{appointment_id}/check-in-qr` |
| `agenda.cabinets.read` | List the clinic's cabinets and read an appointment's cabinet history (the filter chips and the kanban columns). | `GET /agenda/cabinets`, `GET /agenda/appointments/{appointment_id}/cabinet-history` |
| `agenda.cabinets.write` | Create, rename and remove cabinets, and (re)assign an appointment to one. | `POST /agenda/cabinets`, `PUT /agenda/cabinets/{cabinet_id}`, `DELETE /agenda/cabinets/{cabinet_id}`, `PATCH /agenda/appointments/{appointment_id}/cabinet` |

Gated **outside** this namespace: `PATCH /agenda/appointment-treatments/{id}`
(visit-level clinical note + completion flag) requires
`clinical_notes.notes.write`. The row is agenda-owned but the note is the
visit level of the four-level clinical-notes model — issue #60, and the
same cross-module gating precedent india_gst uses with `billing.write`.

Unauthenticated (no permission): `POST /agenda/public/check-in/{token}`
consumes a signed 15-minute token through the canonical status machine
(rate-limited per IP and per token).

## Role assignment

The canonical table is this module's `manifest.role_permissions`
(`backend/app/modules/agenda/__init__.py`), merged at runtime by
`get_role_permissions()`; `core/auth/permissions.py` holds only the core
grants. Today: `admin` and `dentist` get everything, `hygienist` and
`assistant` get `appointments.{read,write}` + `cabinets.read`.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/agenda/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
