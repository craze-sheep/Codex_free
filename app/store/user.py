"""User store — async CRUD operations."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from app.database import get_db


async def create_user(email: str, password: str = "", role: str = "user", balance: float = 0.0) -> dict:
    pw_hash = hashlib.sha256(password.encode()).hexdigest() if password else ""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO users (email, password_hash, role, balance) VALUES (?, ?, ?, ?)",
            (email, pw_hash, role, balance),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "email": email, "role": role, "status": "active", "balance": balance}
    finally:
        await db.close()


async def get_user_by_id(user_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_user_by_email(email: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_users(limit: int = 100, offset: int = 0) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_user(user_id: int, **fields) -> bool:
    if not fields:
        return False
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    db = await get_db()
    try:
        cursor = await db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_user(user_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
