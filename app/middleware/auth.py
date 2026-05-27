"""Bearer token authentication middleware."""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.store.apikey import get_key_by_hash, update_last_used

_security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> dict:
    """Extract Bearer token, validate against api_keys table.

    Returns dict with user_id, key_id, key info.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    key_info = await get_key_by_hash(key_hash)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if key_info["status"] != "active":
        raise HTTPException(status_code=403, detail="API key is suspended")

    # Update last_used_at (fire-and-forget style)
    await update_last_used(key_info["id"])

    return {
        "user_id": key_info["user_id"],
        "key_id": key_info["id"],
        "rate_limit_rpm": key_info["rate_limit_rpm"],
        "rate_limit_tpm": key_info["rate_limit_tpm"],
    }
