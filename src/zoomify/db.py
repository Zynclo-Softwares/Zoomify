"""MongoDB access for Zoomify billing and usage (in-memory fallback when unset)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from zoomify.plans import PlanId, plan_for_id, rate_limit_per_minute
from zoomify.platform_keys import ensure_platform_key_indexes

DEFAULT_DB_NAME = "Zoomify"
USERS = "users"
USAGE_MONTHLY = "usage_monthly"

_memory_users: dict[str, dict[str, Any]] = {}
_memory_usage: dict[tuple[str, str], int] = {}  # (user, "YYYY-MM") -> count
_client = None


def mongodb_database_name() -> str:
    """Logical MongoDB database name (local + deployment via env)."""
    return os.environ.get("MONGODB_DATABASE", DEFAULT_DB_NAME).strip() or DEFAULT_DB_NAME


def mongodb_enabled() -> bool:
    return bool(os.environ.get("MONGODB_URI", "").strip())


def _get_client():
    global _client
    if _client is not None:
        return _client
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        return None
    from pymongo import MongoClient

    _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    return _client


def _users_col():
    client = _get_client()
    if client is None:
        return None
    return client[mongodb_database_name()][USERS]


def _usage_col():
    client = _get_client()
    if client is None:
        return None
    return client[mongodb_database_name()][USAGE_MONTHLY]


def current_period() -> str:
    """Billing period key — the current calendar month in UTC (``YYYY-MM``)."""
    return datetime.now(UTC).strftime("%Y-%m")


def period_resets_at(period: str | None = None) -> str:
    """ISO timestamp of the first instant of the month after ``period``."""
    year, month = (int(x) for x in (period or current_period()).split("-"))
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return datetime(year, month, 1, tzinfo=UTC).isoformat()


def ensure_indexes() -> None:
    users = _users_col()
    usage = _usage_col()
    if users is not None:
        users.create_index("clerkUserId", unique=True)
        users.create_index("stripeCustomerId")
    if usage is not None:
        usage.create_index([("clerkUserId", 1), ("period", 1)], unique=True)
    ensure_platform_key_indexes()


def get_user(clerk_user_id: str) -> dict[str, Any]:
    col = _users_col()
    if col is not None:
        doc = col.find_one({"clerkUserId": clerk_user_id})
        if doc:
            return _normalize_user(doc)
        return _default_user(clerk_user_id)

    doc = _memory_users.get(clerk_user_id)
    if doc:
        return _normalize_user(doc)
    return _default_user(clerk_user_id)


def find_user_id_by_stripe_customer(customer_id: str | None) -> str | None:
    """Resolve a Clerk user id from a Stripe customer id (subscription webhooks)."""
    if not customer_id:
        return None
    col = _users_col()
    if col is not None:
        doc = col.find_one({"stripeCustomerId": customer_id})
        return str(doc["clerkUserId"]) if doc else None
    for clerk_id, doc in _memory_users.items():
        if doc.get("stripeCustomerId") == customer_id:
            return clerk_id
    return None


def _default_user(clerk_user_id: str) -> dict[str, Any]:
    return {
        "clerkUserId": clerk_user_id,
        "plan": "free",
        "subscriptionStatus": "none",
        "stripeCustomerId": None,
        "stripeSubscriptionId": None,
        "currentPeriodEnd": None,
    }


def _normalize_user(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "clerkUserId": doc.get("clerkUserId"),
        "plan": doc.get("plan") or "free",
        "subscriptionStatus": doc.get("subscriptionStatus") or "none",
        "stripeCustomerId": doc.get("stripeCustomerId"),
        "stripeSubscriptionId": doc.get("stripeSubscriptionId"),
        "currentPeriodEnd": doc.get("currentPeriodEnd"),
    }


def upsert_user(clerk_user_id: str, **fields: Any) -> dict[str, Any]:
    col = _users_col()
    fields = {k: v for k, v in fields.items() if v is not None}
    if col is not None:
        col.update_one(
            {"clerkUserId": clerk_user_id},
            {"$set": {**fields, "clerkUserId": clerk_user_id, "updatedAt": datetime.now(UTC)}},
            upsert=True,
        )
        return get_user(clerk_user_id)

    existing = _memory_users.get(clerk_user_id, _default_user(clerk_user_id))
    existing.update(fields)
    existing["clerkUserId"] = clerk_user_id
    _memory_users[clerk_user_id] = existing
    return _normalize_user(existing)


def get_monthly_usage(clerk_user_id: str, period: str | None = None) -> int:
    period = period or current_period()
    col = _usage_col()
    if col is not None:
        doc = col.find_one({"clerkUserId": clerk_user_id, "period": period})
        return int(doc["count"]) if doc else 0
    return _memory_usage.get((clerk_user_id, period), 0)


def increment_monthly_usage(clerk_user_id: str, amount: int = 1) -> int:
    period = current_period()
    col = _usage_col()
    if col is not None:
        result = col.find_one_and_update(
            {"clerkUserId": clerk_user_id, "period": period},
            {
                "$inc": {"count": amount},
                "$setOnInsert": {"clerkUserId": clerk_user_id, "period": period},
            },
            upsert=True,
            return_document=True,
        )
        return int(result["count"])

    key = (clerk_user_id, period)
    _memory_usage[key] = _memory_usage.get(key, 0) + amount
    return _memory_usage[key]


def effective_plan(user: dict[str, Any]) -> PlanId:
    status = user.get("subscriptionStatus") or "none"
    plan = user.get("plan") or "free"
    if status == "active" and plan in ("starter", "pro"):
        return plan  # type: ignore[return-value]
    return "free"


def reset_memory_store() -> None:
    """Clear in-memory billing data (tests)."""
    _memory_users.clear()
    _memory_usage.clear()


def user_billing_status(clerk_user_id: str) -> dict[str, Any]:
    user = get_user(clerk_user_id)
    plan_id = effective_plan(user)
    plan = plan_for_id(plan_id)
    period = current_period()
    used = get_monthly_usage(clerk_user_id, period)
    limit = plan.monthly_limit
    return {
        "plan": plan_id,
        "plan_name": plan.name,
        "subscription_status": user.get("subscriptionStatus") or "none",
        "period": period,
        "monthly_limit": limit,
        "monthly_used": used,
        "monthly_remaining": max(0, limit - used),
        "resets_at": period_resets_at(period),
        "rate_limit_per_minute": rate_limit_per_minute(plan_id),
        "max_image_mb": plan.max_image_mb,
        "max_open_images": plan.max_open_images,
        "current_period_end": user.get("currentPeriodEnd"),
    }
