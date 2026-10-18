"""GDPR erasure contributor for the media module (#657).

Owns the ``media`` coverage scope: radiographs, clinical photos and
uploaded patient files are care records, so this contributor retains them
and reports what it holds. Registered via
``MediaModule.get_erasure_contributors``; pulled by ``gdpr`` inside the
erasure transaction (ADR 0038).
"""

from __future__ import annotations

from app.core.erasure.retention import RetainedScopeContributor


class MediaErasureContributor(RetainedScopeContributor):
    """Retain patient files and imaging on a GDPR erasure.

    A file's ``title``, ``description`` and ``original_filename`` are free
    text, and the stored file itself can contain anything the patient
    signed or the clinic scanned, so all three erasure categories are
    declared. Imaging and scanned consents are
    retained under Art. 17(3)(c)/(h) for as long as medical-records law
    requires.
    """

    scope_name = "media"
    categories = frozenset({"email", "phone", "identity"})
    detail = "Imaging, clinical photos and uploaded patient files retained as care records (Art. 17(3)(c)/(h)); filenames and file contents may quote erased contacts."
