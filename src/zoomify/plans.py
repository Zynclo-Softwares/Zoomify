"""Subscription plan definitions for the Zoomify platform layer (BYOK)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

PlanId = Literal["free", "starter", "pro"]

SubscriptionStatus = Literal["none", "active", "canceled", "past_due"]


@dataclass(frozen=True)
class Plan:
    id: PlanId
    name: str
    price_monthly_usd: int | None
    daily_limit: int | None  # None = unlimited (fair use)
    description: str
    highlights: tuple[str, ...]


PLANS: dict[PlanId, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_monthly_usd=0,
        daily_limit=50,
        description="Try Zoomify with your own OpenRouter key.",
        highlights=(
            "50 extractions per day",
            "Bring your own OpenRouter API key",
            "Smart zoom grid + live trail",
            "Structured JSON when tagged",
        ),
    ),
    "starter": Plan(
        id="starter",
        name="Starter",
        price_monthly_usd=10,
        daily_limit=500,
        description="Daily cap for steady solo use on our server layer.",
        highlights=(
            "500 extractions per day",
            "Full zoom agent platform",
            "BYOK — you pay OpenRouter separately",
            "14-day money-back guarantee",
        ),
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_monthly_usd=25,
        daily_limit=None,
        description="Unlimited extractions for power users (fair use).",
        highlights=(
            "Unlimited extractions*",
            "Fair-use rate limits apply",
            "Priority platform capacity",
            "14-day money-back guarantee",
        ),
    ),
}

YEARLY_DISCOUNT_PERCENT = 15

# Default fair-use caps (requests/min on POST /api/query). Override via .env on the server.
DEFAULT_RATE_LIMIT_FREE_PER_MINUTE = 10
DEFAULT_RATE_LIMIT_STARTER_PER_MINUTE = 30
DEFAULT_RATE_LIMIT_PRO_PER_MINUTE = 20

_RATE_LIMIT_ENV = {
    "free": "RATE_LIMIT_FREE_PER_MINUTE",
    "starter": "RATE_LIMIT_STARTER_PER_MINUTE",
    "pro": "RATE_LIMIT_PRO_PER_MINUTE",
}

_RATE_LIMIT_DEFAULTS = {
    "free": DEFAULT_RATE_LIMIT_FREE_PER_MINUTE,
    "starter": DEFAULT_RATE_LIMIT_STARTER_PER_MINUTE,
    "pro": DEFAULT_RATE_LIMIT_PRO_PER_MINUTE,
}


def _rate_limit_from_env(plan_id: str) -> int:
    env_key = _RATE_LIMIT_ENV.get(plan_id, _RATE_LIMIT_ENV["free"])
    default = _RATE_LIMIT_DEFAULTS.get(plan_id, _RATE_LIMIT_DEFAULTS["free"])
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def rate_limit_per_minute(plan_id: str) -> int:
    """Fair-use requests/min for POST /api/query (env-configurable per plan)."""
    if plan_id in _RATE_LIMIT_DEFAULTS:
        return _rate_limit_from_env(plan_id)
    return _rate_limit_from_env("free")


# Backward-compatible aliases (defaults only — prefer rate_limit_per_minute()).
FREE_RATE_LIMIT_PER_MINUTE = DEFAULT_RATE_LIMIT_FREE_PER_MINUTE
STARTER_RATE_LIMIT_PER_MINUTE = DEFAULT_RATE_LIMIT_STARTER_PER_MINUTE
PRO_RATE_LIMIT_PER_MINUTE = DEFAULT_RATE_LIMIT_PRO_PER_MINUTE


def plan_for_id(plan_id: str | None) -> Plan:
    return PLANS.get(plan_id or "free", PLANS["free"])


def plans_public() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "price_monthly_usd": p.price_monthly_usd,
            "daily_limit": p.daily_limit,
            "description": p.description,
            "highlights": list(p.highlights),
            "unlimited": p.daily_limit is None,
        }
        for p in PLANS.values()
    ]
