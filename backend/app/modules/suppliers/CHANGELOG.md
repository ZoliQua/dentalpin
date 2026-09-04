# Changelog — suppliers module

## Unreleased

- Initial module (roadmap issue #227-1): procurement vendor directory as a
  1:1 extension on top of `contacts` (`contact_type='supplier'`).
- Added `Supplier` model with sourcing-specific fields: `website`,
  `payment_terms`, `lead_time_days`, `is_preferred`.
- Service layer provides atomic CRUD for the `Contact + Supplier` row pairing,
  ensuring both are created/updated together in a single transaction.
- RBAC identical to `contacts`: admin wildcard; dentist/hygienist read-only;
  assistant/receptionist read+write (front-desk procurement management).
- Agent tools exposed: `list_suppliers`, `get_supplier`, `create_supplier`,
  `update_supplier` (wrapping `SupplierService` methods).
- Migration `supp_0001_initial` on own Alembic branch (`suppliers`),
  depending on `contacts@con_0001`.
- `removable=True` — supports full uninstall with roundtrip tests.
- Registered `app/modules/suppliers` in `backend/alembic.ini` `version_locations`
  so the Alembic CLI graph (heads/upgrade) resolves `supp_0001` (CI parity).
- Registered `suppliers` in `pyproject.toml` module entry points so the module
  is discoverable in production (`DENTALPIN_DEV_MODULE_SCAN=False`); closes the
  entry-point parity gap reported by `tests/test_entry_point_parity.py`.
