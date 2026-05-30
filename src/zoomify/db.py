"""MongoDB access for Zoomify billing and usage."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from zoomify.plans import PlanId, plan_for_id

DEFAULT_DB_NAME = "Zoomify"
USERS = "users"
USAGE_DAILY = "usage_daily"

_memory_users: dict[str, dict[str, Any]] = {}
_memory_usage: dict[tuple[str, str], int] = {}
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
    return client[mongodb_database_name()][USAGE_DAILY]


def _today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def ensure_indexes() -> None:
    users = _users_col()
    usage = _usage_col()
    if users is not None:
        users.create_index("clerkUserId", unique=True)
        users.create_index("stripeCustomerId")
    if usage is not None:
        usage.create_index([("clerkUserId", 1), ("date", 1)], unique=True)


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


def get_daily_usage(clerk_user_id: str, date: str | None = None) -> int:
    day = date or _today_utc()
    col = _usage_col()
    if col is not None:
        doc = col.find_one({"clerkUserId": clerk_user_id, "date": day})
        return int(doc["count"]) if doc else 0
    return _memory_usage.get((clerk_user_id, day), 0)


def increment_daily_usage(clerk_user_id: str) -> int:
    day = _today_utc()
    col = _usage_col()
    if col is not None:
        result = col.find_one_and_update(
            {"clerkUserId": clerk_user_id, "date": day},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {"clerkUserId": clerk_user_id, "date": day},
            },
            upsert=True,
            return_document=True,
        )
        return int(result["count"])

    key = (clerk_user_id, day)
    _memory_usage[key] = _memory_usage.get(key, 0) + 1
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
    used = get_daily_usage(clerk_user_id)
    limit = plan.daily_limit
    return {
        "plan": plan_id,
        "plan_name": plan.name,
        "subscription_status": user.get("subscriptionStatus") or "none",
        "daily_limit": limit,
        "daily_used": used,
        "daily_remaining": None if limit is None else max(0, limit - used),
        "unlimited": limit is None,
        "current_period_end": user.get("currentPeriodEnd"),
    }
