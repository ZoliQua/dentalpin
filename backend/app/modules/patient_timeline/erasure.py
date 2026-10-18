"""GDPR erasure contributor for the patient_timeline module (#657).

Owns the ``patient_timeline`` coverage scope. The feed is append-only
accountability data, so this contributor retains it and only reports what
it holds; registered via ``PatientTimelineModule.get_erasure_contributors``
and pulled by ``gdpr`` inside the erasure transaction (ADR 0038).
"""

from __future__ import annotations

from app.core.erasure.retention import RetainedScopeContributor


class PatientTimelineErasureContributor(RetainedScopeContributor):
    """Retain the patient's activity feed on a GDPR erasure.

    ``patient_timeline`` rows carry free text (``title``, ``description``)
    and an arbitrary ``event_data`` JSONB payload, so any of the three
    erasure categories can appear in them, so all three are declared.
    They are retained because the feed is the clinic's record
    of what happened and when (Art. 5(2) accountability, kept under
    Art. 17(3)(b)); rewriting history to hide a contact would destroy the
    audit value the feed exists for.
    """

    scope_name = "patient_timeline"
    categories = frozenset({"email", "phone", "identity"})
    detail = "Append-only activity feed retained as the clinic's record of events (Art. 17(3)(b)); entries may quote erased contacts."
