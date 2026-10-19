---
module: recalls
last_verified_commit: 27442250
---

# Recalls — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload | Subscribers |
|-------|------|---------|-------------|
| `recall.created` | `RecallService.create`; transactional (`db=db`). | `recall_id`, `clinic_id`, `patient_id`, `reason`, `due_month`, `priority`, `status`, … (`_build_event_payload`) | `activity_journal`, `recall_reminders` |
| `recall.snoozed` | `snooze` — due month pushed forward. | the recall payload + `snoozed_months` | — |
| `recall.cancelled` | `cancel`. | the recall payload | — |
| `recall.completed` | `mark_done`. | the recall payload | — |


## Subscribed

All state-changing handlers except the payload-only stub are
**transactional** (ADR 0019): a recall mirrors an appointment, and
`linked_appointment_id` is an FK to a row that only exists in the publisher's
transaction (issue #183).

| Event | Handler | Mode | Effect |
|-------|---------|------|--------|
| `appointment.scheduled` | `events.on_appointment_scheduled` | transactional | Auto-link the single matching pending recall (bails out when ambiguous). |
| `appointment.completed` | `events.on_appointment_completed` | transactional | Mark the linked recall done. |
| `appointment.cancelled` | `events.on_appointment_cancelled` | transactional | Unlink and send the recall back to `pending`. |
| `patient.archived` | `events.on_patient_archived` | transactional | Move active recalls to `needs_review`. |
| `treatment_plan.treatment_completed` | `events.on_treatment_plan_completed` | own-session (payload-only) | Logs only — suggestions are pulled by the frontend. |

GDPR erasure is not an event subscription: the module exposes a
`RecallsErasureContributor` (`erasure.py`), pulled by `gdpr` inside the
erasure transaction (ADR 0038, #546).

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method after `flush()` — the bus runs handlers
   inline, *before* the request commits. Pass `db=db` so transactional
   subscribers can join the transaction (ADR 0019, issue #183).
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
