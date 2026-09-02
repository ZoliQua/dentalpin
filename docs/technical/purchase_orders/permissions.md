---
module: purchase_orders
last_verified_commit: 8b8e9375
---

# purchase_orders — permissions

Returned by `PurchaseOrdersModule.get_permissions()`
(relative names; the registry namespaces them as `purchase_orders.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `purchase_orders.read` | List and view purchase orders, their receipts, and the PDF export | `GET /api/v1/purchase-orders`, `GET /api/v1/purchase-orders/{id}`, `GET /api/v1/purchase-orders/{id}/receipts`, `GET /api/v1/purchase-orders/{id}/receipts/{rid}`, `GET /api/v1/purchase-orders/{id}/pdf` |
| `purchase_orders.write` | Create, edit, transition status, or receive a purchase order | `POST /api/v1/purchase-orders`, `PATCH /api/v1/purchase-orders/{id}`, `POST /api/v1/purchase-orders/{id}/status`, `POST /api/v1/purchase-orders/{id}/receive` |

## Role assignment

Role grants mirror `suppliers`: admin gets wildcard (`*`); dentist and
hygienist get `read` only; assistant and receptionist get `read` + `write`
(front-desk staff run procurement day-to-day).

See `backend/app/modules/purchase_orders/__init__.py` for the canonical role
table (`manifest.role_permissions`).

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/purchase_orders/__init__.py`.
2. Grant it to roles in `manifest.role_permissions`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.