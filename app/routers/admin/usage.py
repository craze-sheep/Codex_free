"""Admin: Usage query + dashboard endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from app.middleware.admin_auth import verify_admin_key
from app.store.usage import query_usage, dashboard_summary

router = APIRouter(prefix="/admin")


@router.get("/usage")
async def get_usage(
    user_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _admin: bool = Depends(verify_admin_key),
):
    """Query usage logs with optional filters."""
    logs = await query_usage(
        user_id=user_id,
        api_key_id=api_key_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return {"data": logs}


@router.get("/dashboard")
async def get_dashboard(_admin: bool = Depends(verify_admin_key)):
    """Today's aggregated stats."""
    summary = await dashboard_summary()
    return summary
