"""Tests for the GDPR erasure registry and contributor contract (ADR 0038, #546)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.erasure.registry import (
    ErasureRegistryError,
    SubjectErasureRegistry,
    erasure_registry,
)
from app.core.erasure.types import ErasureContributor, ErasureCoverage
from app.core.plugins.base import BaseModule
from app.modules.patients.models import Patient


class _StubContributor(ErasureContributor):
    def __init__(self, scope: str):
        self._scope = scope

    @property
    def scope(self) -> str:
        return self._scope

    async def erase(
        self,
        clinic_id: UUID,
        patient_id: UUID,
        erased: list[str],
        retained: list[str],
        db: AsyncSession,
    ) -> ErasureCoverage:
        return ErasureCoverage(scope=self._scope, status="erased", detail="stub")


class _FixtureModule(BaseModule):
    """Throwaway module used only in tests."""

    manifest = {
        "name": "fixture_erasure",
        "version": "0.0.1",
        "summary": "Throwaway fixture.",
        "category": "official",
        "installable": True,
        "auto_install": True,
        "removable": True,
    }

    def __init__(self, contributors: list | None = None):
        self._contributors = contributors or []

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_erasure_contributors(self) -> list:
        return self._contributors


def test_contributor_contract_is_abstract():
    with pytest.raises(TypeError):
        ErasureContributor()  # type: ignore[abstract]


def test_register_from_collects_scopes_sorted():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("b"), _StubContributor("a")]))
    assert registry.scopes() == ["a", "b"]
    assert [c.scope for c in registry.contributors()] == ["a", "b"]


def test_duplicate_scope_raises():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("a")]))
    with pytest.raises(ErasureRegistryError):
        registry.register_from(_FixtureModule([_StubContributor("a")]))


def test_unregister_module_drops_only_its_scopes():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("a")]))
    other = SimpleNamespace(name="other", get_erasure_contributors=lambda: [_StubContributor("b")])
    registry.register_from(other)
    registry.unregister_module("fixture_erasure")
    assert registry.scopes() == ["b"]


def test_clear_resets():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("a")]))
    registry.clear()
    assert registry.scopes() == []
    assert registry.get("a") is None


def test_global_registry_collects_real_modules():
    from app.modules.notifications import NotificationsModule
    from app.modules.recalls import RecallsModule

    erasure_registry.clear()
    try:
        erasure_registry.register_from(NotificationsModule())
        erasure_registry.register_from(RecallsModule())
        assert erasure_registry.scopes() == ["notifications", "recalls"]
    finally:
        erasure_registry.clear()


@pytest.mark.asyncio
async def test_raising_contributor_rolls_back_erasure(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    from app.modules.gdpr.schemas import RetentionPolicyCreate
    from app.modules.gdpr.service import ErasureService, RetentionService

    class _Boom(ErasureContributor):
        @property
        def scope(self) -> str:
            return "boom"

        async def erase(self, clinic_id, patient_id, erased, retained, db):
            raise RuntimeError("contributor failed")

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    # Capture plain ids first: the rollback below expires every ORM object
    # the session has loaded, so attribute access afterwards is MissingGreenlet.
    clinic_id = test_clinic.id
    patient_id = test_patient.id
    erasure_registry.clear()
    try:
        erasure_registry.register_from(_FixtureModule([_Boom()]))
        with pytest.raises(RuntimeError, match="contributor failed"):
            await ErasureService.execute(
                db_session,
                clinic_id,
                patient_id=patient_id,
                categories=["email"],
                rationale="Art.17",
            )
    finally:
        erasure_registry.clear()

    # Nothing committed: patient blanks and the audit log rolled back together.
    await db_session.rollback()
    patient = (
        await db_session.execute(
            select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    assert patient is not None
    assert patient.email is not None
    logs, _ = await ErasureService.list_audit(db_session, clinic_id)
    assert logs == []


# --- Retention-only contributors (#657) ---------------------------------

#: The modules that own a retained coverage scope, with the scope each
#: contributes. Replaces the four rows ``gdpr`` used to hardcode: the
#: ex-``clinical`` row is split across the three modules that actually hold
#: the data, so uninstalling one of them removes only its own row.
RETAINED_SCOPE_OWNERS = {
    "app.modules.patient_timeline:PatientTimelineModule": "patient_timeline",
    "app.modules.budget:BudgetModule": "budget",
    "app.modules.billing:BillingModule": "billing",
    "app.modules.clinical_notes:ClinicalNotesModule": "clinical_notes",
    "app.modules.documents:DocumentsModule": "documents",
    "app.modules.media:MediaModule": "media",
}


def _load(path: str) -> BaseModule:
    import importlib

    module_path, _, class_name = path.partition(":")
    return getattr(importlib.import_module(module_path), class_name)()


def test_retained_scopes_are_owned_by_their_modules():
    registry = SubjectErasureRegistry()
    for path in RETAINED_SCOPE_OWNERS:
        registry.register_from(_load(path))
    assert registry.scopes() == sorted(RETAINED_SCOPE_OWNERS.values())
    # No "clinical" scope any more: there is no clinical module to own it.
    assert registry.get("clinical") is None


@pytest.mark.asyncio
async def test_retained_scopes_report_without_touching_the_session():
    # Every one of these contributors keeps its records, so none of them
    # queries or writes. Passing ``None`` as the session is the assertion:
    # a contributor that touched it would raise AttributeError here.
    clinic_id = UUID(int=1)
    patient_id = UUID(int=2)
    for path, scope in RETAINED_SCOPE_OWNERS.items():
        (contributor,) = _load(path).get_erasure_contributors()
        assert contributor.scope == scope
        row = await contributor.erase(clinic_id, patient_id, ["email"], [], None)  # type: ignore[arg-type]
        assert row.scope == scope
        # Never "erased" — reporting retention is the whole contribution.
        assert row.status == "retained"
        assert row.detail


@pytest.mark.asyncio
async def test_retained_scope_is_not_applicable_without_a_held_category():
    # budget holds only ``signed_by_email`` and billing only
    # ``billing_email``/``billing_tax_id``; neither keeps a phone number, so
    # a phone-only run must not claim to retain one. The free-text and file
    # scopes declare all three categories and stay "retained".
    (budget,) = _load("app.modules.budget:BudgetModule").get_erasure_contributors()
    (billing,) = _load("app.modules.billing:BillingModule").get_erasure_contributors()
    (media,) = _load("app.modules.media:MediaModule").get_erasure_contributors()
    args = (UUID(int=1), UUID(int=2), ["phone"], [])
    assert (await budget.erase(*args, None)).status == "not_applicable"  # type: ignore[arg-type]
    assert (await billing.erase(*args, None)).status == "not_applicable"  # type: ignore[arg-type]
    assert (await media.erase(*args, None)).status == "retained"  # type: ignore[arg-type]
    # billing_tax_id is the patient's national id, so identity does apply.
    identity = (UUID(int=1), UUID(int=2), ["identity"], [])
    assert (await billing.erase(*identity, None)).status == "retained"  # type: ignore[arg-type]
    assert (await budget.erase(*identity, None)).status == "not_applicable"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_inactive_module_produces_no_coverage_row(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """The point of the contract: no contributor, no row (#657).

    ``documents`` is ``auto_install: False``, so a clinic that never
    installed it must not see a ``documents`` row in its DSR coverage —
    reporting one would tell the data subject that data was accounted for
    by a module that is not even there.
    """
    from app.modules.gdpr.schemas import RetentionPolicyCreate
    from app.modules.gdpr.service import ErasureService, RetentionService

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    erasure_registry.clear()
    try:
        erasure_registry.register_from(_load("app.modules.billing:BillingModule"))
        erasure_registry.register_from(_load("app.modules.media:MediaModule"))
        result = await ErasureService.execute(
            db_session,
            test_clinic.id,
            patient_id=test_patient.id,
            categories=["email"],
            rationale="Art.17",
        )
    finally:
        erasure_registry.clear()

    assert result is not None
    scopes = {c.scope for c in result.coverage}
    # patient_record is gdpr's own scope and always reported.
    assert scopes == {"patient_record", "billing", "media"}
    assert "documents" not in scopes
    assert "clinical_notes" not in scopes


def test_every_shipped_contributor_registers_without_conflict():
    """All 59 shipped modules into one registry: no duplicate scope (#657).

    The registry raises on a scope collision, which at boot means the app
    does not start. Catching it here instead keeps a second module from
    claiming, say, ``billing`` and taking the whole install down.
    """
    from app.core.plugins.loader import discover_modules

    registry = SubjectErasureRegistry()
    for module in discover_modules():
        registry.register_from(module)

    scopes = registry.scopes()
    assert len(scopes) == len(set(scopes))
    # The retention scopes that replaced gdpr's hardcoded rows, plus the two
    # scopes that actually redact. ``patient_record`` is gdpr's own and is
    # not a contributor.
    assert set(scopes) == {
        "billing",
        "budget",
        "clinical_notes",
        "documents",
        "media",
        "notifications",
        "patient_timeline",
        "recalls",
    }
