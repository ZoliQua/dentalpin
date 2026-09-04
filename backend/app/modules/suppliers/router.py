"""suppliers HTTP surface — mounted at ``/api/v1/suppliers/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import SupplierCreate, SupplierResponse, SupplierUpdate
from .service import SupplierService

router = APIRouter()


@router.get("", response_model=PaginatedApiResponse[SupplierResponse])
async def list_suppliers(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("suppliers.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(default=None, max_length=200),
    is_preferred: bool | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[SupplierResponse]:
    items, total = await SupplierService.list_suppliers(
        db,
        ctx.clinic_id,
        search=search,
        is_preferred=is_preferred,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[SupplierResponse.from_rows(c, s) for c, s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{supplier_id}", response_model=ApiResponse[SupplierResponse])
async def get_supplier(
    supplier_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("suppliers.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierResponse]:
    result = await SupplierService.get_supplier(db, ctx.clinic_id, supplier_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    contact, supplier = result
    return ApiResponse(data=SupplierResponse.from_rows(contact, supplier))


@router.post("", response_model=ApiResponse[SupplierResponse], status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("suppliers.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierResponse]:
    contact, supplier = await SupplierService.create_supplier(db, ctx.clinic_id, data)
    return ApiResponse(data=SupplierResponse.from_rows(contact, supplier))


@router.patch("/{supplier_id}", response_model=ApiResponse[SupplierResponse])
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("suppliers.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierResponse]:
    result = await SupplierService.get_supplier(db, ctx.clinic_id, supplier_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    contact, supplier = result

    contact, supplier = await SupplierService.update_supplier(db, contact, supplier, data)
    return ApiResponse(data=SupplierResponse.from_rows(contact, supplier))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("suppliers.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await SupplierService.get_supplier(db, ctx.clinic_id, supplier_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    contact, _ = result
    await SupplierService.delete_supplier(db, contact)
