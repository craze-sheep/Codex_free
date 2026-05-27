"""Admin: Provider CRUD + connectivity test."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.middleware.admin_auth import verify_admin_key
from app.models.schemas import ProviderCreate, ProviderUpdate
from app.store.provider import (
    create_provider,
    get_provider_by_id,
    list_providers,
    update_provider,
    delete_provider,
    decrypt_api_key,
)

router = APIRouter(prefix="/admin/providers")


@router.post("")
async def create(data: ProviderCreate, _admin: bool = Depends(verify_admin_key)):
    result = await create_provider(
        name=data.name,
        base_url=data.base_url,
        api_key=data.api_key,
        wire_api=data.wire_api,
        priority=data.priority,
        weight=data.weight,
        max_concurrency=data.max_concurrency,
        failure_threshold=data.failure_threshold,
        recovery_seconds=data.recovery_seconds,
    )
    return result


@router.get("")
async def list_all(_admin: bool = Depends(verify_admin_key)):
    providers = await list_providers()
    return {"data": providers}


@router.get("/{provider_id}")
async def get_one(provider_id: int, _admin: bool = Depends(verify_admin_key)):
    provider = await get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.put("/{provider_id}")
async def update(provider_id: int, data: ProviderUpdate, _admin: bool = Depends(verify_admin_key)):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await update_provider(provider_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"ok": True}


@router.delete("/{provider_id}")
async def delete(provider_id: int, _admin: bool = Depends(verify_admin_key)):
    ok = await delete_provider(provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"ok": True}


@router.post("/{provider_id}/test")
async def test_connectivity(provider_id: int, _admin: bool = Depends(verify_admin_key)):
    """Test upstream provider connectivity by sending a minimal request."""
    provider = await get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    base_url = provider["base_url"].rstrip("/")
    api_key = decrypt_api_key(provider.get("api_key_encrypted", ""))

    try:
        async with httpx.AsyncClient(proxy=settings.proxy_url, timeout=15.0) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        return {
            "status": "ok" if resp.status_code < 400 else "error",
            "http_status": resp.status_code,
            "latency_ms": int(resp.elapsed.total_seconds() * 1000),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
