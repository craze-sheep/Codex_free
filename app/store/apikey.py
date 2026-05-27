"""API Key store — CRUD + key generation."""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from app.database import get_db


def generate_api_key() -> tuple[str, str]:
    """Return (plaintext_key, sha256_hash)."""
    key = "sk-" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key, key_hash


async def create_api_key(
    user_id: int,
    name: str = "",
    rate_limit_rpm: int = 60,
    rate_limit_tpm: int = 100000,
) -> dict:
    """Create a new API key. Returns dict with plaintext key (only time it's visible)."""
    key, key_hash = generate_api_key()
    key_prefix = key[:12] + "..."
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO api_keys (user_id, name, key_hash, key_prefix, rate_limit_rpm, rate_limit_tpm) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, key_hash, key_prefix, rate_limit_rpm, rate_limit_tpm),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "key": key,
            "key_prefix": key_prefix,
            "name": name,
            "user_id": user_id,
        }
    finally:
        await db.close()


async def get_key_by_hash(key_hash: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_keys_by_user(user_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM api_keys WHERE user_id = ? ORDER BY id DESC", (user_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def list_all_keys(limit: int = 100, offset: int = 0) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM api_keys ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_key_by_id(key_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_key(key_id: int, **fields) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [key_id]
    db = await get_db()
    try:
        cursor = await db.execute(f"UPDATE api_keys SET {set_clause} WHERE id = ?", values)
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_key(key_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_last_used(key_id: int) -> None:
    from datetime import datetime
    db = await get_db()
    try:
        await db.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), key_id),
        )
        await db.commit()
    finally:
        await db.close()
