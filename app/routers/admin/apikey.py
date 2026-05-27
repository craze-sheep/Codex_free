"""Admin: API Key CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.admin_auth import verify_admin_key
from app.models.schemas import ApiKeyCreate, ApiKeyUpdate
from app.store.apikey import create_api_key, get_key_by_id, list_all_keys, update_key, delete_key

router = APIRouter(prefix="/admin/apikeys")


@router.post("")
async def create(data: ApiKeyCreate, _admin: bool = Depends(verify_admin_key)):
    result = await create_api_key(
        user_id=data.user_id,
        name=data.name,
        rate_limit_rpm=data.rate_limit_rpm,
        rate_limit_tpm=data.rate_limit_tpm,
    )
    return result


@router.get("")
async def list_all(limit: int = 100, offset: int = 0, _admin: bool = Depends(verify_admin_key)):
    keys = await list_all_keys(limit=limit, offset=offset)
    return {"data": keys}


@router.get("/{key_id}")
async def get_one(key_id: int, _admin: bool = Depends(verify_admin_key)):
    key = await get_key_by_id(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key


@router.put("/{key_id}")
async def update(key_id: int, data: ApiKeyUpdate, _admin: bool = Depends(verify_admin_key)):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await update_key(key_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"ok": True}


@router.delete("/{key_id}")
async def delete(key_id: int, _admin: bool = Depends(verify_admin_key)):
    ok = await delete_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"ok": True}
