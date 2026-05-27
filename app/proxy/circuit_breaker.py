"""Circuit breaker per provider — prevents cascading failures."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class BreakerState:
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed / open / half-open
    failure_threshold: int = 5
    recovery_seconds: int = 60


class CircuitBreaker:
    """In-memory circuit breaker keyed by provider_id."""

    def __init__(self):
        self._breakers: Dict[int, BreakerState] = {}

    def _get(self, provider_id: int, threshold: int = 5, recovery: int = 60) -> BreakerState:
        if provider_id not in self._breakers:
            self._breakers[provider_id] = BreakerState(
                failure_threshold=threshold,
                recovery_seconds=recovery,
            )
        return self._breakers[provider_id]

    def is_open(self, provider_id: int, threshold: int = 5, recovery: int = 60) -> bool:
        """Check if the circuit is open (provider should be skipped)."""
        brk = self._get(provider_id, threshold, recovery)

        if brk.state == "closed":
            return False

        if brk.state == "open":
            # Check if recovery time has passed
            if time.time() - brk.last_failure_time >= brk.recovery_seconds:
                brk.state = "half-open"
                return False  # Allow one request
            return True

        # half-open: allow one request
        return False

    def record_success(self, provider_id: int) -> None:
        """Reset failure count on success."""
        if provider_id in self._breakers:
            brk = self._breakers[provider_id]
            brk.failure_count = 0
            brk.state = "closed"

    def record_failure(self, provider_id: int, threshold: int = 5, recovery: int = 60) -> None:
        """Increment failure count; trip breaker if threshold exceeded."""
        brk = self._get(provider_id, threshold, recovery)
        brk.failure_count += 1
        brk.last_failure_time = time.time()

        if brk.failure_count >= brk.failure_threshold:
            brk.state = "open"


# Global singleton
circuit_breaker = CircuitBreaker()
