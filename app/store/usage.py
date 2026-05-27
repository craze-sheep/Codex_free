"""Usage log store — write + query + dashboard summary."""

from __future__ import annotations

from typing import Optional

from app.database import get_db


async def create_usage_log(
    user_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0.0,
    status: str = "success",
    latency_ms: int = 0,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO usage_logs (user_id, api_key_id, provider_id, request_id, model, "
            "input_tokens, output_tokens, cost, status, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, api_key_id, provider_id, request_id, model,
             input_tokens, output_tokens, cost, status, latency_ms),
        )
        await db.commit()
        return {"id": cursor.lastrowid}
    finally:
        await db.close()


async def query_usage(
    user_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Query usage logs with optional filters."""
    conditions = []
    params: list = []

    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if api_key_id is not None:
        conditions.append("api_key_id = ?")
        params.append(api_key_id)
    if start_time:
        conditions.append("created_at >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("created_at <= ?")
        params.append(end_time)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM usage_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    db = await get_db()
    try:
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def dashboard_summary() -> dict:
    """Today's aggregated stats."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT "
            "  COUNT(*) as total_requests, "
            "  COALESCE(SUM(input_tokens), 0) as total_input_tokens, "
            "  COALESCE(SUM(output_tokens), 0) as total_output_tokens, "
            "  COALESCE(SUM(cost), 0) as total_cost, "
            "  COUNT(DISTINCT user_id) as active_users "
            "FROM usage_logs WHERE date(created_at) = date('now')"
        )
        row = await cursor.fetchone()
        return dict(row) if row else {
            "total_requests": 0, "total_input_tokens": 0,
            "total_output_tokens": 0, "total_cost": 0.0, "active_users": 0,
        }
    finally:
        await db.close()
