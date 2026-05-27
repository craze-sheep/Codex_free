"""Per-key rate limiting middleware (RPM/TPM)."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException


@dataclass
class TokenBucket:
    """Simple in-memory token bucket for rate limiting."""
    rpm_limit: int = 60
    tpm_limit: int = 100000
    rpm_count: int = 0
    tpm_count: int = 0
    window_start: float = field(default_factory=time.time)

    def _maybe_reset(self):
        """Reset counters if window has passed (1 minute)."""
        now = time.time()
        if now - self.window_start >= 60:
            self.rpm_count = 0
            self.tpm_count = 0
            self.window_start = now

    def check_request(self) -> bool:
        """Check if a new request is allowed. Returns True if allowed."""
        self._maybe_reset()
        if self.rpm_count >= self.rpm_limit:
            return False
        self.rpm_count += 1
        return True

    def add_tokens(self, input_tokens: int, output_tokens: int) -> bool:
        """Record token usage. Returns True if within limit."""
        self._maybe_reset()
        total = input_tokens + output_tokens
        if self.tpm_count + total > self.tpm_limit:
            return False
        self.tpm_count += total
        return True


class RateLimiter:
    """In-memory rate limiter keyed by API key ID."""

    def __init__(self):
        self._buckets: dict[int, TokenBucket] = {}

    def _get_bucket(self, key_id: int, rpm: int, tpm: int) -> TokenBucket:
        if key_id not in self._buckets:
            self._buckets[key_id] = TokenBucket(rpm_limit=rpm, tpm_limit=tpm)
        bucket = self._buckets[key_id]
        # Update limits in case they changed
        bucket.rpm_limit = rpm
        bucket.tpm_limit = tpm
        return bucket

    def check_rpm(self, key_id: int, rpm_limit: int) -> None:
        """Raise 429 if RPM exceeded."""
        bucket = self._get_bucket(key_id, rpm_limit, 100000)
        if not bucket.check_request():
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded (RPM)",
                headers={"Retry-After": "60"},
            )

    def record_tpm(self, key_id: int, tpm_limit: int, input_tokens: int, output_tokens: int) -> None:
        """Record token usage, raise 429 if TPM exceeded."""
        bucket = self._get_bucket(key_id, 60, tpm_limit)
        if not bucket.add_tokens(input_tokens, output_tokens):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded (TPM)",
                headers={"Retry-After": "60"},
            )


# Global singleton
rate_limiter = RateLimiter()
