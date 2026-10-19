"""Pydantic schemas for the migration_import HTTP surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportJobResponse(BaseModel):
    """Public view of an :class:`ImportJob`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    created_by: UUID
    status: str
    error: str | None

    original_filename: str
    file_size: int

    source_system: str | None
    exporter_tool: str | None
    exporter_version: str | None
    format_version: str | None
    tenant_label: str | None
    integrity_hash_declared: str | None
    integrity_hash_computed: str | None

    total_entities: int
    processed_entities: int

    import_fiscal_compliance: bool

    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ValidateRequest(BaseModel):
    """Optional passphrase for encrypted DPMFs.

    Sent on POST /jobs/{id}/validate so the passphrase never lives in
    the ImportJob row. Held only in process memory during the call.
    """

    passphrase: str | None = None


class PreviewSample(BaseModel):
    """One sample row in the preview response."""

    canonical_uuid: str
    source_id: str
    payload: dict[str, Any]


class ProfessionalPreviewBreakdown(BaseModel):
    """Counts that help the operator size the professional-filter sliders.

    Only populated for ``entity_type='professional'``. The mapper applies
    the operator-chosen filter at execute time; the preview merely tells
    them how many rows match each signal before they commit.
    """

    deactivated_count: int = 0
    agenda_orphan_count: int = 0
    stale_24m_count: int = 0
    no_activity_count: int = 0
    by_role: dict[str, int] = Field(default_factory=dict)


class EntityPreview(BaseModel):
    entity_type: str
    declared_count: int
    samples: list[PreviewSample] = Field(default_factory=list)
    professional_breakdown: ProfessionalPreviewBreakdown | None = None


class WarningView(BaseModel):
    severity: str
    code: str
    message: str
    entity_type: str | None = None
    source_id: str | None = None


class FilesManifestSummary(BaseModel):
    total: int
    with_sha256: int
    without_sha256: int


class PreviewResponse(BaseModel):
    job: ImportJobResponse
    entities: list[EntityPreview]
    warnings: list[WarningView]
    files: FilesManifestSummary
    # Verifactu opt-in surface — UI hides the checkbox unless both are true.
    verifactu_data_detected: bool
    verifactu_module_installed: bool


class ExecuteRequest(BaseModel):
    """Operator opt-ins for the execute phase."""

    import_fiscal_compliance: bool = False
    # Passphrase repeated only if the file is encrypted; preview already
    # accepted it but execute runs in a fresh BackgroundTask process,
    # so we need it again to re-open the file.
    passphrase: str | None = None

    # --- Professional filtering ---
    # Rows that match any enabled signal are imported as a User but with
    # ``is_active=False`` and ``ClinicMembership.role='assistant'`` so
    # they disappear from the agenda. Historical FKs (appointments,
    # treatments, budgets, payments) still resolve to a real user row.
    # The operator can promote them back from Settings → Users later.
    professional_min_activity_months: int = Field(
        default=24,
        ge=0,
        le=120,
        description=(
            "Soft-deactivate professionals whose source last_activity_at "
            "is older than this many months. Set 0 to disable the check."
        ),
    )
    professional_exclude_agenda_orphans: bool = True
    professional_exclude_inactive_in_source: bool = True
    professional_exclude_non_clinical_roles: bool = False


class WarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    entity_type: str | None
    source_id: str | None
    severity: str
    code: str
    message: str
    raw_data: dict[str, Any] | None
    created_at: datetime


class MappingDecisionResponse(BaseModel):
    """One row of the proposals review page."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    entity_type: str
    canonical_uuid: str

    source_label: str
    source_code: str | None
    source_tipo_odg: int | None

    proposed_action: str
    proposed_target_id: UUID | None
    proposed_target_label: str | None
    proposed_target_category_key: str | None
    proposed_score: float | None

    operator_action: str
    operator_target_id: UUID | None
    operator_target_category_key: str | None
    operator_notes: str | None
    decided_at: datetime | None

    created_at: datetime
    updated_at: datetime


class ProposalsBuildResponse(BaseModel):
    """Summary returned after ``POST /jobs/{id}/proposals``."""

    total: int
    link: int
    fuzzy_link: int
    create: int


class MappingDecisionPatch(BaseModel):
    """PATCH body for a single proposal.

    Set ``operator_action`` to one of: ``accepted`` (use proposal
    verbatim), ``relinked`` (use ``operator_target_id``), ``create_new``
    (force creation in ``operator_target_category_key``), or
    ``ignored`` (drop this Gesdén row from the import).
    """

    operator_action: str = Field(max_length=20)
    operator_target_id: UUID | None = None
    operator_target_category_key: str | None = Field(default=None, max_length=50)
    operator_notes: str | None = None


class BulkAcceptRequest(BaseModel):
    """Accept every pending proposal whose score ≥ ``min_score``.

    Default 0.9 picks only the very confident matches; the operator
    can lower it to widen the bulk-accept set.
    """

    min_score: float = 0.9
    include_exact: bool = True


class BulkAcceptResponse(BaseModel):
    accepted: int
