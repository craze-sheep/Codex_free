"""Upstream provider router — selects the best provider for a model request."""

from __future__ import annotations

import random
from typing import Optional

from app.store.route import find_route


async def select_provider(public_model: str, user_group: str = "*") -> Optional[dict]:
    """Select the best provider for a given model + user group.

    Returns route dict with provider info (base_url, api_key_encrypted, etc.) or None.
    """
    route = await find_route(public_model, user_group)
    if not route:
        # Try wildcard model
        route = await find_route("*", user_group)
    return route


async def select_provider_weighted(routes: list[dict]) -> Optional[dict]:
    """Given multiple matching routes, select one by weight.

    For now, uses priority (already sorted by find_route). Future: weighted random.
    """
    if not routes:
        return None
    return routes[0]
