# Suppliers module

Procurement vendor directory — a 1:1 extension on top of `contacts` for
suppliers, adding sourcing-specific attributes like `website`, `payment_terms`,
`lead_time_days`, and `is_preferred`. Foundation for the procurement suite
(#227-2 through #227-5): `supplier_items`, `purchase_orders`,
`inventory_reorder`, and `supplier_ratings`.

## What it does

Routes mounted at `/api/v1/suppliers/`.

- `GET    /suppliers`          — list, filterable by name/phone/email search and `is_preferred`; `suppliers.read`
- `GET    /suppliers/{id}`     — single supplier; `suppliers.read`
- `POST   /suppliers`          — atomic create (Contact + Supplier in one transaction, 201); `suppliers.write`
- `PATCH  /suppliers/{id}`     — atomic update; `suppliers.write`
- `DELETE /suppliers/{id}`     — soft-delete (sets `Contact.is_active=false`, returns 204); `suppliers.write`

Deletion is soft (not a real database delete) so historical purchase orders
can still reference which supplier they came from, even if that supplier is
no longer active.

## Data model

`Supplier` is a 1:1 extension table where `suppliers.id` is both the PK and
FK to `contacts.id`. Every supplier row corresponds to exactly one
`Contact(contact_type='supplier')`. The service layer ensures atomicity:
creating a supplier creates both rows in a single transaction, updating
touches both rows, and deleting soft-deletes the contact (which cascades
the supplier's `is_active` semantically).

Fields:
- `id`: UUID (PK + FK to `contacts.id`)
- `clinic_id`: UUID (denormalized for rapid multi-tenant filtering)
- `website`: String(2048), nullable
- `payment_terms`: String(255), nullable (e.g., "NET30", "COD")
- `lead_time_days`: Integer, nullable (typical delivery time)
- `is_preferred`: Boolean, default false (used by `inventory_reorder` to
  prioritize where to reorder from)

## Dependencies

`manifest.depends = ["contacts"]` — the base `Contact` entity lives there.
Importing `Contact` and creating rows via `SupplierService` is legal since
it's an explicit dependency. Future modules `supplier_items`, `purchase_orders`,
etc. will depend on `["contacts", "suppliers"]`.

## Permissions

`suppliers.read`, `suppliers.write`. Role grants mirror `contacts`: admin
gets wildcard; dentist/hygienist get read-only; assistant/receptionist get
read+write (front-desk staff manage the vendor directory day-to-day).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_suppliers` | READ | `SupplierService.list_suppliers` | `suppliers.read` |
| `get_supplier` | READ | `SupplierService.get_supplier` | `suppliers.read` |
| `create_supplier` | WRITE | `SupplierService.create_supplier` | `suppliers.write` |
| `update_supplier` | WRITE | `SupplierService.update_supplier` | `suppliers.write` |

## Events emitted / consumed

None.

## Lifecycle

- `installable=True`, `auto_install=False` (optional module, activated
  manually from the admin UI), `removable=True`.
- Migrations on the `suppliers` Alembic branch, depending on
  `contacts@con_0001` (enforces that the `contacts` table exists before we
  create the FK).

## CHANGELOG

See `./CHANGELOG.md`.
