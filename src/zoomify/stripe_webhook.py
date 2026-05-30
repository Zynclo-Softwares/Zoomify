"""Stripe webhook handling for subscription lifecycle."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from zoomify.db import upsert_user

# Map Stripe Payment Link metadata or price lookup keys to plan ids.
PLAN_FROM_METADATA = {
    "starter": "starter",
    "pro": "pro",
}


def _stripe_enabled() -> bool:
    return bool(os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip())


def verify_and_parse(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        # Dev: accept raw JSON without signature when secret unset
        return json.loads(payload)

    import stripe

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip() or None
    return stripe.Webhook.construct_event(payload, sig_header or "", secret)


def _plan_from_subscription(sub: dict[str, Any]) -> str:
    meta = sub.get("metadata") or {}
    plan = meta.get("plan")
    if plan in PLAN_FROM_METADATA:
        return plan
    items = sub.get("items", {}).get("data") or []
    for item in items:
        price = item.get("price") or {}
        lookup = (price.get("lookup_key") or "").lower()
        if "starter" in lookup:
            return "starter"
        if "pro" in lookup:
            return "pro"
        nick = (price.get("nickname") or "").lower()
        if "starter" in nick:
            return "starter"
        if "pro" in nick:
            return "pro"
    return "starter"


def _period_end_iso(sub: dict[str, Any]) -> str | None:
    end = sub.get("current_period_end")
    if not end:
        return None
    return datetime.fromtimestamp(int(end), tz=UTC).isoformat()


def handle_event(event: dict[str, Any]) -> dict[str, str]:
    etype = event.get("type", "")
    data = event.get("data", {}).get("object") or {}

    if etype == "checkout.session.completed":
        return _on_checkout_completed(data)
    if etype in ("customer.subscription.updated", "customer.subscription.created"):
        return _on_subscription_updated(data)
    if etype == "customer.subscription.deleted":
        return _on_subscription_deleted(data)
    return {"status": "ignored", "type": etype}


def _clerk_id_from_obj(obj: dict[str, Any]) -> str | None:
    meta = obj.get("metadata") or {}
    return meta.get("clerk_user_id") or meta.get("clerkUserId")


def _on_checkout_completed(session: dict[str, Any]) -> dict[str, str]:
    clerk_id = _clerk_id_from_obj(session)
    if not clerk_id:
        client_ref = session.get("client_reference_id")
        if client_ref:
            clerk_id = client_ref

    sub_id = session.get("subscription")
    customer_id = session.get("customer")
    plan = (session.get("metadata") or {}).get("plan") or "starter"

    if clerk_id:
        upsert_user(
            clerk_id,
            plan=plan,
            subscriptionStatus="active",
            stripeCustomerId=customer_id,
            stripeSubscriptionId=sub_id,
        )
    return {"status": "ok", "event": "checkout.session.completed"}


def _on_subscription_updated(sub: dict[str, Any]) -> dict[str, str]:
    clerk_id = _clerk_id_from_obj(sub)
    status = sub.get("status") or "none"
    mapped = "active" if status == "active" else status
    plan = _plan_from_subscription(sub)
    fields = {
        "plan": plan if mapped == "active" else "free",
        "subscriptionStatus": mapped,
        "stripeCustomerId": sub.get("customer"),
        "stripeSubscriptionId": sub.get("id"),
        "currentPeriodEnd": _period_end_iso(sub),
    }
    if clerk_id:
        upsert_user(clerk_id, **fields)
    return {"status": "ok", "event": "customer.subscription.updated"}


def _on_subscription_deleted(sub: dict[str, Any]) -> dict[str, str]:
    clerk_id = _clerk_id_from_obj(sub)
    if clerk_id:
        upsert_user(
            clerk_id,
            plan="free",
            subscriptionStatus="canceled",
            stripeSubscriptionId=None,
            currentPeriodEnd=_period_end_iso(sub),
        )
    return {"status": "ok", "event": "customer.subscription.deleted"}


def stripe_configured() -> bool:
    return _stripe_enabled()
