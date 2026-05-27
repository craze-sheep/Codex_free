"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: str
    password: str = ""
    role: str = "user"
    balance: float = 0.0


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    balance: Optional[float] = None


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    status: str
    balance: float
    created_at: str


# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    user_id: int
    name: str = ""
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 100000


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None


class ApiKeyResponse(BaseModel):
    id: int
    user_id: int
    name: str
    key_prefix: str
    status: str
    rate_limit_rpm: int
    rate_limit_tpm: int
    created_at: str
    last_used_at: Optional[str] = None


class ApiKeyCreated(BaseModel):
    """Returned only once on creation — includes the plaintext key."""
    id: int
    key: str
    key_prefix: str
    name: str
    user_id: int


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    wire_api: str = "responses"
    priority: int = 0
    weight: int = 100
    max_concurrency: int = 10
    failure_threshold: int = 5
    recovery_seconds: int = 60


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    wire_api: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    max_concurrency: Optional[int] = None
    failure_threshold: Optional[int] = None
    recovery_seconds: Optional[int] = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    base_url: str
    wire_api: str
    status: str
    priority: int
    weight: int
    max_concurrency: int
    failure_threshold: int
    recovery_seconds: int
    created_at: str


# ---------------------------------------------------------------------------
# Model Route
# ---------------------------------------------------------------------------

class RouteCreate(BaseModel):
    public_model: str
    provider_id: int
    upstream_model: str = ""
    user_group: str = "*"
    enabled: int = 1
    priority: int = 0


class RouteUpdate(BaseModel):
    public_model: Optional[str] = None
    provider_id: Optional[int] = None
    upstream_model: Optional[str] = None
    user_group: Optional[str] = None
    enabled: Optional[int] = None
    priority: Optional[int] = None


class RouteResponse(BaseModel):
    id: int
    public_model: str
    provider_id: int
    upstream_model: str
    user_group: str
    enabled: int
    priority: int


# ---------------------------------------------------------------------------
# Usage / Dashboard
# ---------------------------------------------------------------------------

class UsageQuery(BaseModel):
    user_id: Optional[int] = None
    api_key_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100
    offset: int = 0


class UsageResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    api_key_id: Optional[int] = None
    provider_id: Optional[int] = None
    request_id: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cost: float
    status: str
    latency_ms: int
    created_at: str


class DashboardSummary(BaseModel):
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    active_users: int = 0
