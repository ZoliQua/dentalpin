"""GDPR erasure contributor for the clinical_notes module (#657).

Owns the ``clinical_notes`` coverage scope: notes are care records, so
this contributor retains them and reports what it holds. Registered via
``ClinicalNotesModule.get_erasure_contributors``; pulled by ``gdpr``
inside the erasure transaction (ADR 0038).
"""

from __future__ import annotations

from app.core.erasure.retention import RetainedScopeContributor


class ClinicalNotesErasureContributor(RetainedScopeContributor):
    """Retain clinical notes on a GDPR erasure.

    A note's ``body`` is free prose written during care and can quote any
    of the three erasure categories, so all three are declared. Notes
    are retained under Art. 17(3)(c)/(h): they are
    health data processed for the provision of care, and national
    medical-records retention law sets how long they must be kept.
    Redacting prose would also mean rewriting a clinician's record of what
    was observed.
    """

    scope_name = "clinical_notes"
    categories = frozenset({"email", "phone", "identity"})
    detail = "Clinical notes retained as health-care records (Art. 17(3)(c)/(h)); note text may quote erased contacts."
