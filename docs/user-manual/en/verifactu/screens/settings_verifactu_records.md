---
module: verifactu
screen: records
route: /settings/verifactu/records
related_endpoints:
  - DELETE /api/v1/verifactu/certificate/{cert_id}
  - DELETE /api/v1/verifactu/producer/declaracion
  - GET /api/v1/verifactu/certificate
  - GET /api/v1/verifactu/certificate/history
  - GET /api/v1/verifactu/health
  - GET /api/v1/verifactu/nif-check
  - GET /api/v1/verifactu/producer/defaults
  - GET /api/v1/verifactu/queue
  - GET /api/v1/verifactu/records
  - GET /api/v1/verifactu/records/{record_id}
  - GET /api/v1/verifactu/records/{record_id}/attempts
  - GET /api/v1/verifactu/records/{record_id}/xml
  - GET /api/v1/verifactu/settings
  - GET /api/v1/verifactu/vat-mapping
  - POST /api/v1/verifactu/certificate
  - POST /api/v1/verifactu/queue/process-now
  - POST /api/v1/verifactu/queue/retry-all
  - POST /api/v1/verifactu/queue/{record_id}/retry
  - PUT /api/v1/verifactu/producer
  - PUT /api/v1/verifactu/settings
  - PUT /api/v1/verifactu/vat-mapping/{vat_type_id}
related_permissions:
  - verifactu.settings.read
  - verifactu.settings.configure
  - verifactu.records.read
  - verifactu.queue.manage
  - verifactu.environment.promote
related_paths:
  - backend/app/modules/verifactu/frontend/pages/settings/verifactu/records.vue
last_verified_commit: f3ef82cd
---

# Fiscal ledger

The immutable history of the records submitted to the AEAT. Every row is
one chained record: changing or deleting an accepted record would break
the hash chain, so this page is read-only.

## How to use it

1. Open **Settings > Verifactu > Fiscal ledger**.
2. Narrow the list with the two filters:
   - **State**: all, accepted, accepted with errors, rejected, or pending.
   - **Type**: all, F1, F2, or R1.
   Changing either filter reloads the list from the first page.
3. Move between pages with the arrows at the bottom (50 records per
   page). The total count is shown next to them.

## What each column means

| Column | Meaning |
|--------|---------|
| Date | When the record was created. |
| Type | `F1` full invoice, `F2` simplified invoice, `R1` rectification. |
| Number | Series and number of the invoice the record belongs to. |
| Amount | Total amount sent to the AEAT. |
| State | `accepted`, `accepted_with_errors`, `rejected`, or `pending`. |
| AEAT CSV | The CSV code the AEAT returns once the record is accepted. |

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View the ledger and use the filters | `verifactu.records.read` |

## Troubleshooting

- **The ledger is empty.** The module only writes a record when an
  invoice is issued with Verifactu enabled. Check **Settings > Verifactu**
  for the producer setup and the active environment.
- **A filter returns no rows.** Accepted records only reach that state
  after the AEAT confirms them; use **State: all** to see pending and
  rejected records too.
- **The menu entry is missing.** The module is optional: an admin must
  install it from the module administration and grant
  `verifactu.records.read`.
