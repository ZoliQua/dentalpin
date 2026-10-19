---
module: reports
last_verified_commit: 27442250
---

# Reports

The clinic's reporting hub. `reports` is a **read-only** module
that aggregates data from the business modules (billing, budgets,
agenda) into dashboards. The dashboard shows a drill-down chip for
each report family it can reach, including the payments report owned by
the `payments` module (see
[payment reports](../payments/screens/reports_payments.md)); each chip
appears only for users who hold that family's read permission.

## Screens

- [Reports dashboard](./screens/reports.md) — entry point with one
  card per report family.
- [Billing](./screens/reports_billing.md) — totals invoiced, by
  series, by payment method, evolution.
- [Budgets](./screens/reports_budgets.md) — conversion, time in
  each state, rejection / closure reasons.
- [Agenda and occupancy](./screens/reports_scheduling.md) — busy
  hours, no-shows, cancellations, professional mix.

## Quick reference

| Action | Required permission |
|--------|---------------------|
| View the dashboard | any of the three permissions below |
| See billing reports | `reports.billing.read` |
| See budget reports | `reports.budgets.read` |
| See agenda reports | `reports.scheduling.read` |
| See payment reports (contributed by `payments`) | `payments.reports.read` |
| See financial aging + trend | `reports.financial.read` |
| See patient demographics + visits | `reports.patient_stats.read` |
| See operational productivity | `reports.operational.read` |

## New in v0.2.0 — report families

- **Financial** (`reports.financial.read`): outstanding aging buckets
  and monthly issued totals, invoice axis only, with `?format=csv`.
  The dashboard aging card reads these numbers.
- **Patient stats** (`reports.patient_stats.read`): as-of-now
  demographics (age bands, gender, area with explicit unknowns) and
  new-vs-returning visit frequency, with `?format=csv`. No dedicated
  screen yet — ask the copilot or export the CSV.
- **Operational** (`reports.operational.read`): completed
  appointments per professional and cabinet plus the treatment-plan
  pipeline, with `?format=csv`. No dedicated screen yet.

## Related modules

- **Billing, budgets, agenda** — sources of the aggregated reports.
- **Payments** — owns the payments report the dashboard links to.
- **Catalog, patients** — references and enrichments in aggregated
  rows (treatment category, patient, professional).
