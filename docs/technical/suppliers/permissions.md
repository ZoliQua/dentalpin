---
module: suppliers
last_verified_commit: 53b6f476
---

# Suppliers — permissions

Returned by `SuppliersModule.get_permissions()`
(relative names; the registry namespaces them as `suppliers.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `suppliers.read` | List and view supplier details | `GET /api/v1/suppliers`, `GET /api/v1/suppliers/{id}` |
| `suppliers.write` | Create, update, or soft-delete a supplier | `POST /api/v1/suppliers`, `PATCH /api/v1/suppliers/{id}`, `DELETE /api/v1/suppliers/{id}` |

## Role assignment

Role grants mirror `contacts`: admin gets wildcard (`*`); dentist and
hygienist get `read` only; assistant and receptionist get `read` + `write`
(front-desk staff manage the vendor directory day-to-day).

See `backend/app/modules/suppliers/__init__.py` for the canonical role
table (`manifest.role_permissions`).

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/suppliers/__init__.py`.
2. Grant it to roles in `manifest.role_permissions`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
