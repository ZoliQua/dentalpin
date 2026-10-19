---
module: billing
last_verified_commit: 27442250
---

# Billing — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload | Subscribers |
|-------|------|---------|-------------|
| `invoice.issued` | `InvoiceWorkflowService.issue_invoice` — draft → issued, after the number is allocated. | `clinic_id`, `invoice_id`, `patient_id`, `invoice_number`, `total`, `issued_by`, `occurred_at` | `patient_timeline` |
| `invoice.paid` | `recalc_invoice_status` lands on `paid` (a payment or allocation covers the total). | `clinic_id`, `invoice_id`, `patient_id`, `invoice_number`, `total`, `total_paid`, `occurred_at` | `patient_timeline`, `verifactu` (updates `compliance_data['ES']`) |
| `invoice.sent` | `POST /invoices/{id}/send` — published **transactionally** (`db=db`, ADR 0019). | `clinic_id`, `invoice_id`, `patient_id`, `send_method`, `recipient_email`, `custom_message` | `activity_journal`, `notifications` |


## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `payment.allocated` | `events.py:on_payment_allocated` (**transactional**, ADR 0019) | Reconcile `invoice_payments` with the payment's budget allocations (`payment_bridge.reconcile_payment`): impute FIFO over the budget's open invoices / unlink on reallocation, then recompute status. Issue #178. |
| `payment.refunded` | `events.py:on_payment_refunded` (**transactional**) | Recompute status of invoices whose `invoice_payments` link the refunded payment (`paid → partial`, `partial → issued`), inside the refund's transaction. |
| `clinic.created` | `events.py:on_clinic_created` | Create the default `FAC` (invoice) and `RECT` (credit note) series when the clinic has none. |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method (after `flush`; pass `db=db` if a
   subscriber must react inside your transaction — ADR 0019).
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
