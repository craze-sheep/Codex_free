"""Admin key authentication middleware."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_security = HTTPBearer(auto_error=False)


async def verify_admin_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> bool:
    """Validate admin key from Authorization header."""
    if not settings.admin_key:
        raise HTTPException(status_code=500, detail="ADMIN_KEY not configured")

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if credentials.credentials != settings.admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    return True
