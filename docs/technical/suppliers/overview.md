---
module: suppliers
last_verified_commit: 53b6f476
---

# suppliers — overview

Procurement vendor directory as a 1:1 extension of `contacts` for suppliers,
adding sourcing-specific attributes (website, payment terms, lead time,
preferred status). Foundation for the procurement suite (#227-2 through
#227-5).

## What it is

Admin-authenticated CRUD under `/api/v1/suppliers/` (JWT + RBAC). A clinic
manages its supplier directory separately from general contacts, with
atomic creation ensuring both `Contact(type='supplier')` and `Supplier`
rows are created together in a single transaction.

Routes:
- `GET /api/v1/suppliers` — list with search and `is_preferred` filtering
- `GET /api/v1/suppliers/{id}` — get one
- `POST /api/v1/suppliers` — atomic create (201)
- `PATCH /api/v1/suppliers/{id}` — atomic update
- `DELETE /api/v1/suppliers/{id}` — soft-delete (204)

## Data model

`suppliers` — 1:1 extension table where `suppliers.id` is both PK and FK to
`contacts.id`. Fields: `website`, `payment_terms`, `lead_time_days`,
`is_preferred`. Denormalizes `clinic_id` for rapid multi-tenant filtering
without a join.

Migration: `supp_0001_initial` on own Alembic branch (`suppliers`),
depending on `contacts@con_0001`.

## Service layer

`SupplierService` encapsulates the atomic lifecycle:
- `create_supplier`: Creates `Contact(contact_type='supplier')` + `Supplier`
  in one transaction.
- `list_suppliers`: Paginated join query with search filtering across
  contact name/phone/email and `is_preferred` boolean filter.
- `get_supplier`: Retrieves the composite `(Contact, Supplier)` tuple,
  clinic-scoped.
- `update_supplier`: Updates both rows atomically.
- `delete_supplier`: Soft-deletes the contact (sets `is_active=false`).

## Agent tools

Four tools exposed: `list_suppliers`, `get_supplier`, `create_supplier`,
`update_supplier`. Each wraps the corresponding service method, filters by
`ctx.clinic_id`, and returns native values (UUID/datetime coerced at the
registry).

## Tenancy

Every query filters by `clinic_id`; a cross-clinic supplier id 404s rather
than 403s, matching repo convention.

## Constraints

Own Alembic branch (`suppliers`), depending on `contacts@con_0001` — no FK
into other module tables. `manifest.depends = ["contacts"]`.

See [`./permissions.md`](./permissions.md) and [`./events.md`](./events.md)
for full detail.
