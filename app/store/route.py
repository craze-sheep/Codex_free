"""Model Route store — CRUD + route lookup."""

from __future__ import annotations

from typing import Optional

from app.database import get_db


async def create_route(
    public_model: str,
    provider_id: int,
    upstream_model: str = "",
    user_group: str = "*",
    enabled: int = 1,
    priority: int = 0,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO model_routes (public_model, provider_id, upstream_model, user_group, enabled, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (public_model, provider_id, upstream_model, user_group, enabled, priority),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "public_model": public_model, "provider_id": provider_id}
    finally:
        await db.close()


async def get_route_by_id(route_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM model_routes WHERE id = ?", (route_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_routes() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM model_routes ORDER BY priority DESC, id ASC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def find_route(public_model: str, user_group: str = "*") -> Optional[dict]:
    """Find the best matching route for a model + user group."""
    db = await get_db()
    try:
        # Exact model match first, then wildcard
        cursor = await db.execute(
            "SELECT mr.*, p.base_url, p.api_key_encrypted, p.name as provider_name, "
            "p.wire_api, p.status as provider_status "
            "FROM model_routes mr "
            "JOIN providers p ON mr.provider_id = p.id "
            "WHERE mr.enabled = 1 AND p.status = 'active' "
            "AND (mr.public_model = ? OR mr.public_model = '*') "
            "AND (mr.user_group = ? OR mr.user_group = '*') "
            "ORDER BY mr.public_model DESC, mr.priority DESC "
            "LIMIT 1",
            (public_model, user_group),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_enabled_models() -> list[str]:
    """Return deduplicated list of enabled public_model names."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT DISTINCT mr.public_model FROM model_routes mr "
            "JOIN providers p ON mr.provider_id = p.id "
            "WHERE mr.enabled = 1 AND p.status = 'active' AND mr.public_model != '*'"
        )
        rows = await cursor.fetchall()
        return [r["public_model"] for r in rows]
    finally:
        await db.close()


async def update_route(route_id: int, **fields) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [route_id]
    db = await get_db()
    try:
        cursor = await db.execute(f"UPDATE model_routes SET {set_clause} WHERE id = ?", values)
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_route(route_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM model_routes WHERE id = ?", (route_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
