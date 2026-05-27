"""Singleton httpx AsyncClient with connection pooling.

CRITICAL: Never create a new client per request — reuse this singleton.
LLM requests need long read timeouts (up to 5 minutes for streaming).
"""

from __future__ import annotations

import httpx

from app.config import settings

# Singleton client — created once, reused everywhere, closed on shutdown.
http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the singleton httpx client. Raises if not initialized."""
    if http_client is None:
        raise RuntimeError("HTTP client not initialized — call init_http_client() first")
    return http_client


def init_http_client() -> httpx.AsyncClient:
    """Create and return the singleton httpx AsyncClient."""
    global http_client
    proxy = settings.proxy_url
    http_client = httpx.AsyncClient(
        proxy=proxy,
        timeout=httpx.Timeout(
            connect=10.0,    # TCP connect timeout
            read=300.0,      # 5 min read timeout (LLMs are slow)
            write=10.0,      # send timeout
            pool=5.0,        # waiting for pool slot
        ),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=30,
        ),
        transport=httpx.AsyncHTTPTransport(retries=1),
    )
    return http_client


async def close_http_client() -> None:
    """Close the singleton client on shutdown."""
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None
