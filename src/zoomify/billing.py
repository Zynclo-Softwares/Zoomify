"""Usage quotas, rate limits, and Stripe checkout links."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from zoomify.db import increment_daily_usage, user_billing_status
from zoomify.plans import YEARLY_DISCOUNT_PERCENT, PLANS, rate_limit_per_minute

_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def checkout_links() -> dict[str, str | None]:
    return {
        "starter_monthly": _env("STRIPE_LINK_STARTER_MONTHLY"),
        "starter_yearly": _env("STRIPE_LINK_STARTER_YEARLY"),
        "pro_monthly": _env("STRIPE_LINK_PRO_MONTHLY"),
        "pro_yearly": _env("STRIPE_LINK_PRO_YEARLY"),
    }


def billing_plans_payload() -> dict:
    links = checkout_links()
    yearly_factor = 1 - YEARLY_DISCOUNT_PERCENT / 100
    plans = []
    for p in PLANS.values():
        monthly = p.price_monthly_usd
        yearly = None
        if monthly and monthly > 0:
            yearly = round(monthly * 12 * yearly_factor)
        entry = {
            "id": p.id,
            "name": p.name,
            "price_monthly_usd": p.price_monthly_usd,
            "price_yearly_usd": yearly,
            "yearly_discount_percent": YEARLY_DISCOUNT_PERCENT if monthly else None,
            "daily_limit": p.daily_limit,
            "description": p.description,
            "highlights": list(p.highlights),
            "unlimited": p.daily_limit is None,
            "checkout": None,
        }
        if p.id == "starter":
            entry["checkout"] = {
                "monthly": links["starter_monthly"],
                "yearly": links["starter_yearly"],
            }
        elif p.id == "pro":
            entry["checkout"] = {
                "monthly": links["pro_monthly"],
                "yearly": links["pro_yearly"],
            }
        plans.append(entry)

    return {
        "plans": plans,
        "yearly_discount_percent": YEARLY_DISCOUNT_PERCENT,
        "money_back_days": 14,
        "metered_endpoint": "POST /api/query",
        "premium_schema": {
            "name": "Premium schema service",
            "description": (
                "Custom extraction schemas tailored to your documents — "
                "invoices, forms, IDs, and domain-specific layouts."
            ),
            "highlights": [
                "Custom JSON schema design",
                "Validation + prompt tuning",
                "Private schema registry per team",
                "Delivered by Zynclo engineers",
            ],
            "contact": "form",
        },
    }


def _rate_limit_for_plan(plan_id: str) -> int:
    return rate_limit_per_minute(plan_id)


def _check_rate_limit(clerk_user_id: str, plan_id: str) -> None:
    limit = _rate_limit_for_plan(plan_id)
    now = time.monotonic()
    window = _rate_windows[clerk_user_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} requests/min). Upgrade or wait a moment.",
        )
    window.append(now)


def enforce_query_quota(clerk_user_id: str) -> dict:
    """Check quota before query; returns billing snapshot. Raises HTTPException if blocked."""
    status = user_billing_status(clerk_user_id)
    plan_id = status["plan"]
    limit = status["daily_limit"]
    used = status["daily_used"]

    _check_rate_limit(clerk_user_id, plan_id)

    if limit is not None and used >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily limit reached ({used}/{limit} extractions). "
                "Upgrade your plan for more capacity."
            ),
        )
    return status


def record_query_usage(clerk_user_id: str) -> dict:
    count = increment_daily_usage(clerk_user_id)
    status = user_billing_status(clerk_user_id)
    status["daily_used"] = count
    if status["daily_remaining"] is not None:
        status["daily_remaining"] = max(0, status["daily_limit"] - count)
    return status
