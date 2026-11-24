"""Subscription plan definitions for the Zoomify MCP server.

A **request** is one metered MCP tool call (``open_image`` or ``zoom``).
Navigation (``undo`` / ``redo`` / ``restore`` / ``view``), ``usage`` and skill
lookups are free. Allowances reset on the 1st of each month (UTC).
"""

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
    monthly_limit: int  # metered requests per calendar month
    rate_limit_per_minute: int  # default fair-use burst cap (env-overridable)
    max_image_mb: int  # largest image / PDF accepted by open_image and uploads
    max_open_images: int  # concurrent zoom sessions kept alive per account
    description: str
    highlights: tuple[str, ...]


PLANS: dict[PlanId, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_monthly_usd=0,
        monthly_limit=1_000,
        rate_limit_per_minute=20,
        max_image_mb=20,
        max_open_images=3,
        description="Everything you need to try Zoomify with your own agent.",
        highlights=(
            "1,000 requests per month",
            "All zoom tools and agent skills",
            "Images and PDFs up to 20 MB",
            "No credit card required",
        ),
    ),
    "starter": Plan(
        id="starter",
        name="Starter",
        price_monthly_usd=10,
        monthly_limit=25_000,
        rate_limit_per_minute=60,
        max_image_mb=50,
        max_open_images=10,
        description="For individuals running agents on documents every day.",
        highlights=(
            "25,000 requests per month",
            "60 requests per minute",
            "Images and PDFs up to 50 MB",
            "14-day money-back guarantee",
        ),
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_monthly_usd=25,
        monthly_limit=150_000,
        rate_limit_per_minute=120,
        max_image_mb=100,
        max_open_images=25,
        description="For teams and automated pipelines at volume.",
        highlights=(
            "150,000 requests per month",
            "120 requests per minute",
            "Images and PDFs up to 100 MB",
            "14-day money-back guarantee",
        ),
    ),
}

YEARLY_DISCOUNT_PERCENT = 15

_RATE_LIMIT_ENV = {
    "free": "RATE_LIMIT_FREE_PER_MINUTE",
    "starter": "RATE_LIMIT_STARTER_PER_MINUTE",
    "pro": "RATE_LIMIT_PRO_PER_MINUTE",
}


def plan_for_id(plan_id: str | None) -> Plan:
    return PLANS.get(plan_id or "free", PLANS["free"])  # type: ignore[arg-type]


def rate_limit_per_minute(plan_id: str) -> int:
    """Fair-use metered requests/min for a plan (env-configurable per plan)."""
    plan = plan_for_id(plan_id)
    raw = os.environ.get(_RATE_LIMIT_ENV[plan.id], "").strip()
    if not raw:
        return plan.rate_limit_per_minute
    try:
        return max(1, int(raw))
    except ValueError:
        return plan.rate_limit_per_minute


def plans_public() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "price_monthly_usd": p.price_monthly_usd,
            "monthly_limit": p.monthly_limit,
            "rate_limit_per_minute": rate_limit_per_minute(p.id),
            "max_image_mb": p.max_image_mb,
            "max_open_images": p.max_open_images,
            "description": p.description,
            "highlights": list(p.highlights),
        }
        for p in PLANS.values()
    ]
