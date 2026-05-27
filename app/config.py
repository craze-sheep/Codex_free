"""Configuration loader — reads from .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: int(_env("PORT", "3000")))
    admin_key: str = field(default_factory=lambda: _env("ADMIN_KEY", ""))
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "data/codex_relay.db")
    )
    http_proxy: str = field(default_factory=lambda: _env("HTTP_PROXY", ""))
    https_proxy: str = field(default_factory=lambda: _env("HTTPS_PROXY", ""))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    encryption_key: str = field(default_factory=lambda: _env("ENCRYPTION_KEY", ""))

    @property
    def proxy_url(self) -> str | None:
        """Return the proxy URL for httpx, or None if not configured."""
        return self.https_proxy or self.http_proxy or None


settings = Settings()
