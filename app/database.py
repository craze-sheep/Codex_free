"""SQLite database connection and schema initialization (aiosqlite)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_DB_PATH: str = settings.database_url


def _resolve_db_path() -> str:
    """Ensure parent directory exists and return absolute path."""
    p = Path(_DB_PATH)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


async def get_db() -> aiosqlite.Connection:
    """Return a new aiosqlite connection (caller must close)."""
    db = await aiosqlite.connect(_resolve_db_path())
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL DEFAULT '',
    role          TEXT    NOT NULL DEFAULT 'user',   -- admin / user
    status        TEXT    NOT NULL DEFAULT 'active',  -- active / suspended
    balance       REAL    NOT NULL DEFAULT 0.0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name           TEXT    NOT NULL DEFAULT '',
    key_hash       TEXT    UNIQUE NOT NULL,
    key_prefix     TEXT    NOT NULL DEFAULT '',
    status         TEXT    NOT NULL DEFAULT 'active',   -- active / suspended
    rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
    rate_limit_tpm INTEGER NOT NULL DEFAULT 100000,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    last_used_at   TEXT
);

CREATE TABLE IF NOT EXISTS providers (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT    UNIQUE NOT NULL,
    base_url           TEXT    NOT NULL,
    api_key_encrypted  TEXT    NOT NULL DEFAULT '',
    wire_api           TEXT    NOT NULL DEFAULT 'responses',  -- responses / chat_completions
    status             TEXT    NOT NULL DEFAULT 'active',      -- active / disabled
    priority           INTEGER NOT NULL DEFAULT 0,
    weight             INTEGER NOT NULL DEFAULT 100,
    max_concurrency    INTEGER NOT NULL DEFAULT 10,
    failure_threshold  INTEGER NOT NULL DEFAULT 5,
    recovery_seconds   INTEGER NOT NULL DEFAULT 60,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_routes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    public_model   TEXT    NOT NULL,
    provider_id    INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    upstream_model TEXT    NOT NULL DEFAULT '',
    user_group     TEXT    NOT NULL DEFAULT '*',
    enabled        INTEGER NOT NULL DEFAULT 1,
    priority       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    api_key_id    INTEGER,
    provider_id   INTEGER,
    request_id    TEXT,
    model         TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost          REAL    NOT NULL DEFAULT 0.0,
    status        TEXT    NOT NULL DEFAULT 'success',  -- success / error
    latency_ms    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id    ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash   ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_model_routes_model  ON model_routes(public_model);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id  ON usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created  ON usage_logs(created_at);
"""


async def init_db() -> None:
    """Create tables if they don't exist."""
    db = await get_db()
    try:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()
        logger.info("Database initialized at %s", _resolve_db_path())
    finally:
        await db.close()
