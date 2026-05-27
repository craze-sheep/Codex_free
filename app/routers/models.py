"""GET /v1/models — list available models."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.middleware.auth import verify_api_key
from app.store.route import list_enabled_models

router = APIRouter()


@router.get("/v1/models")
async def get_models(_auth: dict = Depends(verify_api_key)):
    """Return available models in OpenAI-compatible format."""
    models = await list_enabled_models()

    return {
        "object": "list",
        "data": [
            {
                "id": m,
                "object": "model",
                "created": 0,
                "owned_by": "codex-relay",
            }
            for m in models
        ],
    }
