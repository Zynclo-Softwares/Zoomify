"""Usage quotas, rate limits, and Stripe checkout links."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from zoomify.db import increment_monthly_usage, user_billing_status
from zoomify.plans import PLANS, YEARLY_DISCOUNT_PERCENT, rate_limit_per_minute

# Tools that count against the monthly allowance. Everything else is free.
METERED_TOOLS = ("open_image", "zoom")

_rate_windows: dict[str, deque[float]] = defaultdict(deque)


class QuotaExceeded(Exception):
    """Raised when a metered request is blocked by a plan limit."""

    def __init__(self, message: str, *, kind: str, status: dict | None = None) -> None:
        super().__init__(message)
        self.kind = kind  # "rate" | "monthly"
        self.status = status


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
        yearly = round(monthly * 12 * yearly_factor) if monthly else None
        checkout = None
        if p.id != "free":
            checkout = {
                "monthly": links[f"{p.id}_monthly"],
                "yearly": links[f"{p.id}_yearly"],
            }
        plans.append(
            {
                "id": p.id,
                "name": p.name,
                "price_monthly_usd": monthly,
                "price_yearly_usd": yearly,
                "yearly_discount_percent": YEARLY_DISCOUNT_PERCENT if monthly else None,
                "monthly_limit": p.monthly_limit,
                "rate_limit_per_minute": rate_limit_per_minute(p.id),
                "max_image_mb": p.max_image_mb,
                "max_open_images": p.max_open_images,
                "description": p.description,
                "highlights": list(p.highlights),
                "checkout": checkout,
            }
        )

    return {
        "plans": plans,
        "yearly_discount_percent": YEARLY_DISCOUNT_PERCENT,
        "money_back_days": 14,
        "metered_tools": list(METERED_TOOLS),
        "custom_skills": {
            "name": "Custom skills",
            "description": (
                "Domain-specific agent skills tuned to your documents — "
                "drawing standards, forms, title blocks, and house conventions."
            ),
            "highlights": [
                "Skills written for your document types",
                "Extraction checklists and output formats",
                "Higher limits and private deployments",
                "Delivered by Zynclo engineers",
            ],
            "contact": "form",
        },
    }


def _check_rate_limit(clerk_user_id: str, plan_id: str) -> None:
    limit = rate_limit_per_minute(plan_id)
    now = time.monotonic()
    window = _rate_windows[clerk_user_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise QuotaExceeded(
            f"Rate limit exceeded ({limit} requests/min on this plan). "
            "Wait a few seconds and retry.",
            kind="rate",
        )
    window.append(now)


def reset_rate_limits() -> None:
    """Clear in-memory rate windows (tests)."""
    _rate_windows.clear()


def enforce_quota(clerk_user_id: str) -> dict:
    """Check limits before a metered request. Raises :class:`QuotaExceeded` if blocked."""
    status = user_billing_status(clerk_user_id)
    limit = status["monthly_limit"]
    used = status["monthly_used"]

    if used >= limit:
        raise QuotaExceeded(
            f"Monthly request limit reached ({used:,}/{limit:,} on the "
            f"{status['plan_name']} plan). It resets on {status['resets_at'][:10]} (UTC); "
            "upgrade at /pricing for a higher allowance.",
            kind="monthly",
            status=status,
        )
    _check_rate_limit(clerk_user_id, status["plan"])
    return status


def record_usage(clerk_user_id: str, status: dict | None = None) -> dict:
    """Count one metered request and return the updated billing snapshot."""
    count = increment_monthly_usage(clerk_user_id)
    status = dict(status) if status else user_billing_status(clerk_user_id)
    status["monthly_used"] = count
    status["monthly_remaining"] = max(0, status["monthly_limit"] - count)
    return status
