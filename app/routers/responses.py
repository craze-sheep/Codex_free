"""POST /v1/responses — core proxy endpoint (streaming + non-streaming)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.middleware.auth import verify_api_key
from app.proxy.forwarder import forward_request

router = APIRouter()


@router.post("/v1/responses")
async def handle_responses(
    request: Request,
    auth: dict = Depends(verify_api_key),
):
    """Proxy /v1/responses to upstream provider."""
    return await forward_request(
        request=request,
        user_id=auth["user_id"],
        key_id=auth["key_id"],
        rate_limit_rpm=auth["rate_limit_rpm"],
        rate_limit_tpm=auth["rate_limit_tpm"],
    )
