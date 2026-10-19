"""Agent tools for the staff_tasks board. Thin wrappers over StaffTaskService."""

from __future__ import annotations

from datetime import date as date_cls
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import StaffTaskCreate, StaffTaskUpdate, TaskPriority, TaskStatus
from .service import StaffTaskService


class ListTasksArgs(BaseModel):
    status: TaskStatus | None = None
    due_before: date_cls | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CreateTaskArgs(BaseModel):
    title: str = Field(min_length=1)
    details: str | None = None
    priority: TaskPriority = "normal"
    due_date: date_cls | None = None


class UpdateTaskStatusArgs(BaseModel):
    task_id: UUID
    status: TaskStatus


def _summary(task) -> dict:
    return {
        "id": task.id,  # native UUID — the registry's jsonify coerces
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date,
    }


async def _list(ctx: AgentContext, params: ListTasksArgs) -> dict:
    items, total = await StaffTaskService.list_tasks(
        ctx.db,
        ctx.clinic_id,
        task_status=params.status,
        due_before=params.due_before,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "tasks": [_summary(t) for t in items]}


async def _create(ctx: AgentContext, params: CreateTaskArgs) -> dict:
    payload = StaffTaskCreate(
        title=params.title,
        details=params.details,
        priority=params.priority,
        due_date=params.due_date,
    )
    # AgentContext carries no user identity — agent-created tasks are
    # attributed to no staff row; the actor trail lives in agent_audit_logs.
    return _summary(await StaffTaskService.create_task(ctx.db, ctx.clinic_id, payload, None))


async def _update_status(ctx: AgentContext, params: UpdateTaskStatusArgs) -> dict:
    task = await StaffTaskService.update_task(
        ctx.db,
        ctx.clinic_id,
        params.task_id,
        StaffTaskUpdate(status=params.status),
        None,
    )
    return _summary(task)


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_staff_tasks",
            description=(
                "List tasks on the clinic's staff handoff board, optionally "
                "filtered by status or due date."
            ),
            parameters=ListTasksArgs,
            handler=_list,
            permissions=["staff_tasks.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_staff_task",
            description="Create a new task on the staff handoff board.",
            parameters=CreateTaskArgs,
            handler=_create,
            permissions=["staff_tasks.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="update_staff_task_status",
            description="Change a staff task's status (open/claimed/done/cancelled).",
            parameters=UpdateTaskStatusArgs,
            handler=_update_status,
            permissions=["staff_tasks.write"],
            category=ToolCategory.WRITE,
        ),
    ]
