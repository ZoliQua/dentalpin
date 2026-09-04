"""Treatment plan module database models.

Note: clinical-notes models live in the ``clinical_notes`` module since
issue #60. The ``clinical_notes`` and ``clinical_note_attachments`` tables
remain in the database, but ownership of the schema/migrations moved.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User
    from app.modules.agenda.models import Appointment
    from app.modules.budget.models import Budget
    from app.modules.catalog.models import TreatmentCatalogItem
    from app.modules.odontogram.models import Treatment
    from app.modules.patients.models import Patient


class TreatmentPlan(Base, TimestampMixin):
    """Treatment plan that groups treatments for a patient.

    Orchestrates the patient workflow by linking treatments from the odontogram
    with budgets and appointments. Communicates with other modules via event bus.
    """

    __tablename__ = "treatment_plans"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)

    # Identification
    plan_number: Mapped[str] = mapped_column(String(50))  # PLAN-2024-0001
    title: Mapped[str | None] = mapped_column(String(200))

    # Status workflow: draft → pending → active → completed → archived
    # Terminal non-completed state: closed (with closure_reason). Reactivable
    # back to draft. See ADR 0006 and docs/workflows/plan-budget-flow.md.
    status: Mapped[str] = mapped_column(String(20), default="draft")

    # Closure metadata (set when status becomes ``closed``).
    # Allowed closure_reason values:
    #   rejected_by_patient | expired | cancelled_by_clinic |
    #   patient_abandoned  | other
    closure_reason: Mapped[str | None] = mapped_column(String(50))
    closure_note: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Confirmation timestamp (set on draft → pending). Used for
    # pipeline analytics and "days waiting" sorting.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Budget integration (one-to-one)
    budget_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("budgets.id"), unique=True, index=True
    )

    # Assignments
    assigned_professional_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Clinical notes
    diagnosis_notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    patient: Mapped["Patient"] = relationship()
    budget: Mapped["Budget | None"] = relationship()
    assigned_professional: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_professional_id]
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    items: Mapped[list["PlannedTreatmentItem"]] = relationship(
        back_populates="treatment_plan",
        cascade="all, delete-orphan",
        order_by="PlannedTreatmentItem.sequence_order",
    )

    __table_args__ = (
        UniqueConstraint("clinic_id", "plan_number", name="uq_treatment_plan_number"),
        Index("idx_treatment_plans_patient", "patient_id"),
        Index("idx_treatment_plans_status", "clinic_id", "status"),
        Index("idx_treatment_plans_budget", "budget_id"),
        # Tab "Cerrados" of the pipeline filters by closed_at desc.
        Index(
            "idx_treatment_plans_clinic_status_closed",
            "clinic_id",
            "status",
            "closed_at",
        ),
    )


class PlannedTreatmentItem(Base, TimestampMixin):
    """Individual treatment within a plan.

    Always references a single Treatment (from the odontogram module). Globalness,
    per-tooth / multi-tooth, pricing and catalog link all live on the Treatment.
    """

    __tablename__ = "planned_treatment_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    treatment_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatment_plans.id", ondelete="CASCADE"), index=True
    )

    # Single link to Treatment. Unique: no two items may reference the same Treatment.
    treatment_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatments.id", ondelete="CASCADE"), index=True
    )

    # Ordering and status
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending|completed|cancelled

    # Completion tracking
    completed_without_appointment: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    # Doctor responsible for performing this treatment line. Snapshot from the
    # plan's assigned_professional_id at creation time; once set it is
    # independent — changing the plan-level doctor does not cascade here unless
    # the caller passes ``reassign_pending_items=True`` on the plan update.
    assigned_professional_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    treatment_plan: Mapped["TreatmentPlan"] = relationship(back_populates="items")
    treatment: Mapped["Treatment"] = relationship()
    completer: Mapped["User | None"] = relationship(foreign_keys=[completed_by])
    assigned_professional: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_professional_id]
    )
    sessions: Mapped[list["PlannedTreatmentItemSession"]] = relationship(
        back_populates="plan_item",
        cascade="all, delete-orphan",
        order_by="PlannedTreatmentItemSession.sequence",
    )

    __table_args__ = (
        UniqueConstraint("treatment_id", name="uq_planned_item_treatment"),
        Index("idx_planned_items_plan", "treatment_plan_id"),
        Index("idx_planned_items_treatment", "treatment_id"),
        Index("idx_planned_items_status", "treatment_plan_id", "status"),
        Index(
            "idx_planned_items_plan_professional",
            "treatment_plan_id",
            "assigned_professional_id",
        ),
    )


class PlannedTreatmentItemSession(Base, TimestampMixin):
    """One billable / executable step of a ``PlannedTreatmentItem``.

    Snapshotted from ``CatalogItemSession`` at plan-add time. After
    creation the session is independent — editing the catalog template
    does not retro-affect existing plan instances. Once a session is
    marked ``completed`` its label and amount are immutable.
    """

    __tablename__ = "planned_treatment_item_sessions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("planned_treatment_items.id", ondelete="CASCADE"), index=True
    )

    sequence: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending|completed|cancelled

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    plan_item: Mapped["PlannedTreatmentItem"] = relationship(back_populates="sessions")
    completer: Mapped["User | None"] = relationship(foreign_keys=[completed_by])

    __table_args__ = (
        UniqueConstraint("plan_item_id", "sequence", name="uq_plan_item_session_sequence"),
        Index("idx_pti_session_plan_item", "plan_item_id"),
        Index("ix_pti_session_plan_item_status", "plan_item_id", "status"),
    )


class AppointmentTreatment(Base):
    """Plan↔appointment link rows (``appointment_treatments``).

    Owned by treatment_plan since #337: ``planned_treatment_item_id`` is
    NOT NULL — a row cannot exist without a planned item, so this was
    never agenda data with a plan reference but the plan-side visit
    bridge. All three FKs are declarable from here (agenda and catalog
    are in ``manifest.depends``); from agenda's side the edge was a
    manifest cycle (#309). The table itself is unchanged — created by
    ag_0001, future ALTERs live on the ``tp`` branch.

    The ``backref`` installs ``Appointment.treatments`` (cascade
    delete-orphan, ordered) so agenda keeps reading its appointments'
    treatments duck-typed without ever importing this class; its
    queries eager-load through the planned-work provider.
    """

    __tablename__ = "appointment_treatments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    appointment_id: Mapped[UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    planned_treatment_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("planned_treatment_items.id"), index=True
    )
    catalog_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("treatment_catalog_items.id", ondelete="SET NULL"), nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_in_appointment: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    appointment: Mapped["Appointment"] = relationship(
        backref=backref(
            "treatments",
            cascade="all, delete-orphan",
            order_by="AppointmentTreatment.display_order",
        )
    )
    planned_item: Mapped["PlannedTreatmentItem"] = relationship()
    catalog_item: Mapped["TreatmentCatalogItem | None"] = relationship()
