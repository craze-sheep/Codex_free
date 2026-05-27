"""Provider store — CRUD + AES encryption for upstream API keys."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from app.config import settings
from app.database import get_db


# ---------------------------------------------------------------------------
# AES-256-GCM encryption helpers
# ---------------------------------------------------------------------------

def _get_aes_key() -> bytes:
    """Derive 32-byte key from ENCRYPTION_KEY config."""
    raw = settings.encryption_key.encode()
    return hashlib.sha256(raw).digest()


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt upstream API key with AES-256-GCM. Returns base64 string."""
    if not plaintext:
        return ""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _get_aes_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()
    except ImportError:
        # Fallback: base64 obfuscation (not secure, but functional)
        return base64.b64encode(plaintext.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt upstream API key."""
    if not encrypted:
        return ""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _get_aes_key()
        data = base64.b64decode(encrypted)
        nonce, ct = data[:12], data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode()
    except ImportError:
        return base64.b64decode(encrypted).decode()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_provider(
    name: str,
    base_url: str,
    api_key: str = "",
    wire_api: str = "responses",
    priority: int = 0,
    weight: int = 100,
    max_concurrency: int = 10,
    failure_threshold: int = 5,
    recovery_seconds: int = 60,
) -> dict:
    encrypted_key = encrypt_api_key(api_key) if api_key else ""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO providers (name, base_url, api_key_encrypted, wire_api, priority, weight, "
            "max_concurrency, failure_threshold, recovery_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, base_url, encrypted_key, wire_api, priority, weight,
             max_concurrency, failure_threshold, recovery_seconds),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "name": name, "base_url": base_url, "status": "active"}
    finally:
        await db.close()


async def get_provider_by_id(provider_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM providers WHERE id = ?", (provider_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_providers() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM providers ORDER BY priority DESC, id ASC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_provider(provider_id: int, **fields) -> bool:
    if not fields:
        return False
    # Encrypt api_key if being updated
    if "api_key" in fields:
        fields["api_key_encrypted"] = encrypt_api_key(fields.pop("api_key"))
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [provider_id]
    db = await get_db()
    try:
        cursor = await db.execute(f"UPDATE providers SET {set_clause} WHERE id = ?", values)
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_provider(provider_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_decrypted_key(provider_id: int) -> str:
    """Return decrypted API key for a provider."""
    provider = await get_provider_by_id(provider_id)
    if not provider:
        return ""
    return decrypt_api_key(provider.get("api_key_encrypted", ""))
