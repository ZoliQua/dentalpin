"""GDPR erasure contributor for the billing module (#657).

Owns the ``billing`` coverage scope: an issued invoice is a fiscal record
that must not change, so this contributor retains it and reports what it
holds. Registered via ``BillingModule.get_erasure_contributors``; pulled
by ``gdpr`` inside the erasure transaction (ADR 0038).
"""

from __future__ import annotations

from app.core.erasure.retention import RetainedScopeContributor


class BillingErasureContributor(RetainedScopeContributor):
    """Retain the fiscal snapshot on an invoice during a GDPR erasure.

    An invoice freezes the billing party at issue time:
    ``billing_email`` (the ``email`` category) and ``billing_tax_id``,
    the NIF/CIF that is the patient's national id for an individual (the
    ``identity`` category). ``phone`` is not held here, so a phone-only
    run reports ``not_applicable``. Both are retained under Art. 17(3)(b)
    — national bookkeeping law requires the issued document to stay as
    issued, and an e-invoice already registered with the tax authority
    cannot be altered at all.
    """

    scope_name = "billing"
    categories = frozenset({"email", "identity"})
    detail = "Issued invoices keep their fiscal snapshot (`billing_email`, `billing_tax_id`) unchanged, as bookkeeping law requires (Art. 17(3)(b))."
