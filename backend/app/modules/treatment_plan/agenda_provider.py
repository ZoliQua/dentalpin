"""treatment_plan's implementation of agenda's planned-work contract.

Registered on every boot from ``TreatmentPlanModule.__init__`` (issue
#309). The import direction is legal — ``agenda`` is in this module's
``manifest.depends`` — which is exactly why the implementation lives
here and not in agenda: the manifest graph stays acyclic while agenda
keeps its booking-time validation and eager loading.

Keep the validation rules in sync with the plan state machine (see the
module CLAUDE.md): ``draft``/``pending``/``active`` plans are bookable
(#108), terminal ones are not; an item is bookable only while
``pending``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.agenda.models import Appointment
from app.modules.odontogram.models import Treatment

from .models import AppointmentTreatment, PlannedTreatmentItem


class TreatmentPlanPlannedWorkProvider:
    def appointment_loader_options(self) -> list[Any]:
        return [
            selectinload(Appointment.treatments).options(
                selectinload(AppointmentTreatment.planned_item).options(
                    selectinload(PlannedTreatmentItem.treatment).options(
                        selectinload(Treatment.teeth),
                        selectinload(Treatment.catalog_item),
                    ),
                    selectinload(PlannedTreatmentItem.treatment_plan),
                ),
                selectinload(AppointmentTreatment.catalog_item),
            )
        ]

    async def validate_bookable_items(
        self,
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        planned_item_ids: list[UUID],
    ) -> list[str]:
        result = await db.execute(
            select(PlannedTreatmentItem)
            .options(selectinload(PlannedTreatmentItem.treatment_plan))
            .where(PlannedTreatmentItem.id.in_(planned_item_ids))
        )
        items = {item.id: item for item in result.scalars().all()}

        errors: list[str] = []
        for item_id in planned_item_ids:
            item = items.get(item_id)
            if not item:
                errors.append(f"Treatment item {item_id} not found")
                continue
            if item.clinic_id != clinic_id:
                errors.append(f"Treatment item {item_id} not found")
                continue
            plan = item.treatment_plan
            if not plan or plan.patient_id != patient_id:
                errors.append(f"Treatment item {item_id} does not belong to patient")
                continue
            # `pending` (plan confirmed, budget not yet accepted) is bookable
            # on purpose: an unconfirmed `draft` already is, so confirming a
            # plan must not take that away — clinics book the first visit while
            # the patient is still deciding (#108). Terminal states stay out.
            if plan.status not in ("active", "draft", "pending"):
                errors.append(f"Treatment item {item_id} belongs to {plan.status} plan")
                continue
            if item.status != "pending":
                errors.append(f"Treatment item {item_id} is already {item.status}")

        return errors

    async def attach_planned_items(
        self,
        db: AsyncSession,
        appointment_id: UUID,
        planned_item_ids: list[UUID],
    ) -> None:
        for order, planned_item_id in enumerate(planned_item_ids):
            catalog_item_id = None
            planned_item = await db.get(PlannedTreatmentItem, planned_item_id)
            if planned_item:
                await db.refresh(planned_item, ["treatment"])
                if planned_item.treatment:
                    catalog_item_id = planned_item.treatment.catalog_item_id
            db.add(
                AppointmentTreatment(
                    appointment_id=appointment_id,
                    planned_treatment_item_id=planned_item_id,
                    catalog_item_id=catalog_item_id,
                    display_order=order,
                )
            )
        await db.flush()

    async def visit_note_row(
        self,
        db: AsyncSession,
        clinic_id: UUID,
        appointment_treatment_id: UUID,
    ) -> tuple[Any, Any] | None:
        result = await db.execute(
            select(AppointmentTreatment, Appointment)
            .join(Appointment, AppointmentTreatment.appointment_id == Appointment.id)
            .where(
                AppointmentTreatment.id == appointment_treatment_id,
                Appointment.clinic_id == clinic_id,
            )
        )
        row = result.first()
        return (row[0], row[1]) if row else None
