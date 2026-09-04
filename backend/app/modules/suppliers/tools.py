"""Agent tools for the suppliers module. Thin wrappers over SupplierService."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import SupplierCreate
from .service import SupplierService


class ListSuppliersArgs(BaseModel):
    search: str | None = None
    is_preferred: bool | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GetSupplierArgs(BaseModel):
    supplier_id: str = Field(description="UUID of the supplier")


class CreateSupplierArgs(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
    website: str | None = None
    payment_terms: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    is_preferred: bool = False


class UpdateSupplierArgs(BaseModel):
    supplier_id: str = Field(description="UUID of the supplier")
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
    website: str | None = None
    payment_terms: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    is_preferred: bool | None = None


def _supplier_summary(contact, supplier) -> dict:
    """Return native values — jsonify at the registry coerces UUID/datetime."""
    return {
        "id": contact.id,
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email,
        "website": supplier.website,
        "payment_terms": supplier.payment_terms,
        "lead_time_days": supplier.lead_time_days,
        "is_preferred": supplier.is_preferred,
        "is_active": contact.is_active,
    }


async def _list_suppliers(ctx: AgentContext, params: ListSuppliersArgs) -> dict:
    items, total = await SupplierService.list_suppliers(
        ctx.db,
        ctx.clinic_id,
        search=params.search,
        is_preferred=params.is_preferred,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "suppliers": [_supplier_summary(c, s) for c, s in items]}


async def _get_supplier(ctx: AgentContext, params: GetSupplierArgs) -> dict:
    from uuid import UUID

    result = await SupplierService.get_supplier(ctx.db, ctx.clinic_id, UUID(params.supplier_id))
    if not result:
        return {"error": "Supplier not found"}
    contact, supplier = result
    return _supplier_summary(contact, supplier)


async def _create_supplier(ctx: AgentContext, params: CreateSupplierArgs) -> dict:
    payload = SupplierCreate(
        name=params.name,
        phone=params.phone,
        email=params.email,
        address=params.address,
        notes=params.notes,
        website=params.website,
        payment_terms=params.payment_terms,
        lead_time_days=params.lead_time_days,
        is_preferred=params.is_preferred,
    )
    contact, supplier = await SupplierService.create_supplier(ctx.db, ctx.clinic_id, payload)
    return _supplier_summary(contact, supplier)


async def _update_supplier(ctx: AgentContext, params: UpdateSupplierArgs) -> dict:
    from uuid import UUID

    from .schemas import SupplierUpdate

    result = await SupplierService.get_supplier(ctx.db, ctx.clinic_id, UUID(params.supplier_id))
    if not result:
        return {"error": "Supplier not found"}
    contact, supplier = result

    # Only forward the fields the agent actually set — passing every attribute
    # explicitly would mark them all as "set" and wipe the omitted ones.
    payload = SupplierUpdate(**params.model_dump(exclude_unset=True, exclude={"supplier_id"}))
    contact, supplier = await SupplierService.update_supplier(ctx.db, contact, supplier, payload)
    return _supplier_summary(contact, supplier)


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="list_suppliers",
            description="List suppliers with optional filtering by name/phone/email or preferred status",
            category=ToolCategory.READ,
            permissions=["suppliers.read"],
            handler=_list_suppliers,
            parameters=ListSuppliersArgs,
        ),
        Tool(
            name="get_supplier",
            description="Get detailed information about a specific supplier by ID",
            category=ToolCategory.READ,
            permissions=["suppliers.read"],
            handler=_get_supplier,
            parameters=GetSupplierArgs,
        ),
        Tool(
            name="create_supplier",
            description="Create a new supplier (procurement vendor) in the clinic directory",
            category=ToolCategory.WRITE,
            permissions=["suppliers.write"],
            handler=_create_supplier,
            parameters=CreateSupplierArgs,
        ),
        Tool(
            name="update_supplier",
            description="Update an existing supplier's information",
            category=ToolCategory.WRITE,
            permissions=["suppliers.write"],
            handler=_update_supplier,
            parameters=UpdateSupplierArgs,
        ),
    ]
