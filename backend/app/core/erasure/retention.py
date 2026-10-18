"""Base contributor for scopes a legal basis retains (ADR 0038, issue #657)."""

from __future__ import annotations

from typing import ClassVar, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erasure.types import ErasureContributor, ErasureCoverage


class RetainedScopeContributor(ErasureContributor):
    """A scope that erases nothing because Art. 17(3) retains its records.

    Several modules hold patient data that a partial erasure must report
    but must not touch — invoices, signed quotes, care records. Their
    whole contribution is an honest coverage row, so they share the
    status logic here and declare only what differs:

    ``scope_name``
        the coverage scope, unique across the registry.
    ``categories``
        the erasure categories this scope actually holds copies of.
        Required, and spelled out per module rather than defaulted: a
        scope that keeps no phone number must report ``not_applicable``
        for a phone-only run instead of claiming to retain one, and only
        the module knows its own columns.
    ``detail``
        the retention claim the DSR shows, naming the legal basis.

    :meth:`erase` writes nothing and queries nothing: the records stay, so
    there is no redaction to perform. A module that later starts redacting
    should implement :class:`~app.core.erasure.types.ErasureContributor`
    directly instead of extending this.
    """

    scope_name: ClassVar[str]
    categories: ClassVar[frozenset[str]]
    detail: ClassVar[str]

    @property
    def scope(self) -> str:
        return self.scope_name

    async def erase(
        self,
        clinic_id: UUID,
        patient_id: UUID,
        erased: list[str],
        retained: list[str],
        db: AsyncSession,
    ) -> ErasureCoverage:
        """Report retention for this scope without writing anything.

        ``erased`` lists the categories cleared from the *patient record*;
        this scope keeps its own copies regardless, so the status is never
        ``erased`` — that is the point of the row. A run that touched none
        of :attr:`categories` (including one whose only category has no
        field mapping at all) gets ``not_applicable``.
        """
        requested = set(erased) | set(retained)
        status: Literal["erased", "retained", "not_applicable"] = (
            "retained" if self.categories & requested else "not_applicable"
        )
        return ErasureCoverage(scope=self.scope, status=status, detail=self.detail)
