"""Admin: Model Route CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.admin_auth import verify_admin_key
from app.models.schemas import RouteCreate, RouteUpdate
from app.store.route import create_route, get_route_by_id, list_routes, update_route, delete_route

router = APIRouter(prefix="/admin/routes")


@router.post("")
async def create(data: RouteCreate, _admin: bool = Depends(verify_admin_key)):
    result = await create_route(
        public_model=data.public_model,
        provider_id=data.provider_id,
        upstream_model=data.upstream_model,
        user_group=data.user_group,
        enabled=data.enabled,
        priority=data.priority,
    )
    return result


@router.get("")
async def list_all(_admin: bool = Depends(verify_admin_key)):
    routes = await list_routes()
    return {"data": routes}


@router.get("/{route_id}")
async def get_one(route_id: int, _admin: bool = Depends(verify_admin_key)):
    route = await get_route_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.put("/{route_id}")
async def update(route_id: int, data: RouteUpdate, _admin: bool = Depends(verify_admin_key)):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await update_route(route_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="Route not found")
    return {"ok": True}


@router.delete("/{route_id}")
async def delete(route_id: int, _admin: bool = Depends(verify_admin_key)):
    ok = await delete_route(route_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Route not found")
    return {"ok": True}
