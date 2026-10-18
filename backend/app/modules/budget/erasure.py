"""GDPR erasure contributor for the budget module (#657).

Owns the ``budget`` coverage scope: signed quotes are evidence of an
accepted estimate, so this contributor retains them and reports what it
holds. Registered via ``BudgetModule.get_erasure_contributors``; pulled by
``gdpr`` inside the erasure transaction (ADR 0038).
"""

from __future__ import annotations

from app.core.erasure.retention import RetainedScopeContributor


class BudgetErasureContributor(RetainedScopeContributor):
    """Retain signed quotes and their signer contact on a GDPR erasure.

    The only patient contact this module copies is
    ``BudgetSignature.signed_by_email`` — there is no phone or national-id
    column here — so ``categories`` is ``email`` and a phone-only or
    identity-only run correctly reports ``not_applicable``. The signature
    binds a named signer to a document hash; blanking its email would
    break that binding, which is what makes the acceptance provable
    (Art. 17(3)(e), establishment of legal claims).
    """

    scope_name = "budget"
    categories = frozenset({"email"})
    detail = "Signed quotes keep the signer's email so the signature stays bound to the document (Art. 17(3)(e))."
