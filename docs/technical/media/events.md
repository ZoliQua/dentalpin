---
module: media
last_verified_commit: 27442250
---

# Media — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload | Subscribers |
|-------|------|---------|-------------|
| `document.uploaded` | `DocumentService.create_document` — **every** upload, photos and X-rays included; transactional (`db=db`). | `document_id`, `clinic_id`, `patient_id`, `title`, `document_type`, `media_kind`, `media_category`, `media_subtype` | `patient_timeline` (drops `media_kind` `photo`/`xray`, which get their own card from `media.photo_uploaded`) |
| `media.photo_uploaded` | Same call, additionally, when `media_kind` is an image kind; transactional. | `document_id`, `clinic_id`, `patient_id`, `title`, `media_kind`, `media_category`, `media_subtype`, `captured_at` (nullable) | `imaging_viewer`, `patient_timeline` |
| `document.deleted` | `DocumentService.delete_document`. | `document_id`, `clinic_id`, `patient_id` | — |
| `media.pair_created` | `pair` — before/after pairing set on two documents of the same patient. | `clinic_id`, `patient_id`, `document_a_id`, `document_b_id` | `patient_timeline` |
| `media.pair_removed` | `unpair`. | `clinic_id`, `patient_id`, `document_id`, `former_partner_id` | — |
| `media.attachment_linked` | `AttachmentService.link` — a document attached to an owner through the registry. | `attachment_id`, `clinic_id`, `document_id`, `owner_type`, `owner_id`, `patient_id` | — |
| `media.attachment_unlinked` | `AttachmentService.unlink` (the document stays). | `attachment_id`, `clinic_id`, `document_id`, `owner_type`, `owner_id` | — |


## Subscribed

| Event | Handler | Mode | Effect |
|-------|---------|------|--------|
| `patient.archived` | `__init__.py::MediaModule._on_patient_archived` | transactional (ADR 0019) | Soft-archive the patient's documents, atomically with the archive itself. |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method after `flush()` — the bus runs handlers
   inline, *before* the request commits. Pass `db=db` so transactional
   subscribers can join the transaction (ADR 0019, issue #183).
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
