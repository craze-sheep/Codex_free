"""Request forwarder — proxies /v1/responses to upstream providers."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.middleware.rate_limit import rate_limiter
from app.proxy.circuit_breaker import circuit_breaker
from app.proxy.router import select_provider
from app.store.provider import decrypt_api_key
from app.store.usage import create_usage_log

logger = logging.getLogger(__name__)


async def forward_request(
    request: Request,
    user_id: int,
    key_id: int,
    rate_limit_rpm: int = 60,
    rate_limit_tpm: int = 100000,
) -> JSONResponse | StreamingResponse:
    """Forward a /v1/responses request to the best upstream provider."""

    # Read request body
    body = await request.body()
    try:
        req_data = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    public_model = req_data.get("model", "")
    is_stream = req_data.get("stream", False)

    # Rate limit check (RPM)
    rate_limiter.check_rpm(key_id, rate_limit_rpm)

    # Route to provider
    route = await select_provider(public_model)
    if not route:
        return JSONResponse(
            {"error": {"message": f"No route found for model '{public_model}'", "type": "invalid_request_error"}},
            status_code=404,
        )

    provider_id = route["provider_id"]

    # Circuit breaker check
    if circuit_breaker.is_open(
        provider_id,
        route.get("failure_threshold", 5),
        route.get("recovery_seconds", 60),
    ):
        return JSONResponse(
            {"error": {"message": "Provider temporarily unavailable (circuit open)", "type": "server_error"}},
            status_code=503,
        )

    # Prepare upstream request
    base_url = route["base_url"].rstrip("/")
    upstream_url = f"{base_url}/responses"

    # Decrypt upstream API key
    upstream_key = decrypt_api_key(route.get("api_key_encrypted", ""))

    # Rewrite model if upstream_model is specified
    upstream_model = route.get("upstream_model", "")
    if upstream_model:
        req_data["model"] = upstream_model

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {upstream_key}",
    }

    # Add proxy config
    proxy_url = settings.proxy_url

    start_time = time.perf_counter()

    try:
        if is_stream:
            return await _forward_stream(upstream_url, headers, req_data, proxy_url, provider_id, user_id, key_id, public_model, start_time)
        else:
            return await _forward_sync(upstream_url, headers, req_data, proxy_url, provider_id, user_id, key_id, public_model, start_time)
    except httpx.ConnectError as e:
        circuit_breaker.record_failure(provider_id)
        logger.error("Upstream connect error: %s", e)
        return JSONResponse(
            {"error": {"message": "Failed to connect to upstream provider", "type": "server_error"}},
            status_code=502,
        )
    except Exception as e:
        circuit_breaker.record_failure(provider_id)
        logger.error("Forward error: %s", e)
        return JSONResponse(
            {"error": {"message": "Internal proxy error", "type": "server_error"}},
            status_code=500,
        )


async def _forward_sync(
    url: str,
    headers: dict,
    body: dict,
    proxy: Optional[str],
    provider_id: int,
    user_id: int,
    key_id: int,
    model: str,
    start_time: float,
) -> JSONResponse:
    """Non-streaming forward."""
    async with httpx.AsyncClient(proxy=proxy, timeout=120.0) as client:
        resp = await client.post(url, headers=headers, json=body)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    if resp.status_code != 200:
        circuit_breaker.record_failure(provider_id)
        return JSONResponse(resp.json(), status_code=resp.status_code)

    circuit_breaker.record_success(provider_id)

    resp_data = resp.json()

    # Async usage logging
    asyncio.create_task(_log_usage(resp_data, user_id, key_id, provider_id, model, elapsed_ms, "success"))

    return JSONResponse(resp_data, status_code=200)


async def _forward_stream(
    url: str,
    headers: dict,
    body: dict,
    proxy: Optional[str],
    provider_id: int,
    user_id: int,
    key_id: int,
    model: str,
    start_time: float,
) -> StreamingResponse:
    """SSE streaming forward."""

    async def event_generator():
        total_input = 0
        total_output = 0
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=300.0) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code != 200:
                        error_body = b""
                        async for chunk in resp.aiter_bytes():
                            error_body += chunk
                        circuit_breaker.record_failure(provider_id)
                        yield f"data: {json.dumps({'error': 'Upstream error'})}\n\n"
                        return

                    circuit_breaker.record_success(provider_id)

                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                event = json.loads(data_str)
                                # Extract usage if present
                                if "usage" in event:
                                    total_input = event["usage"].get("input_tokens", total_input)
                                    total_output = event["usage"].get("output_tokens", total_output)
                            except json.JSONDecodeError:
                                pass
                            yield f"{line}\n\n"
                        elif line.strip() == "":
                            continue
                        else:
                            yield f"{line}\n\n"

        except Exception as e:
            logger.error("Stream error: %s", e)
            circuit_breaker.record_failure(provider_id)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        asyncio.create_task(_log_usage(
            {"usage": {"input_tokens": total_input, "output_tokens": total_output}},
            user_id, key_id, provider_id, model, elapsed_ms, "success",
        ))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _log_usage(
    resp_data: dict,
    user_id: int,
    key_id: int,
    provider_id: int,
    model: str,
    latency_ms: int,
    status: str,
) -> None:
    """Extract usage from response and log it."""
    usage = resp_data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    await create_usage_log(
        user_id=user_id,
        api_key_id=key_id,
        provider_id=provider_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status=status,
        latency_ms=latency_ms,
    )
