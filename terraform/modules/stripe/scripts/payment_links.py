#!/usr/bin/env python3
"""Ensure Zoomify Stripe Payment Links exist; emit URLs for Terraform external data."""

from __future__ import annotations

import json
import os
import sys

import stripe

LINK_SPECS = (
    ("starter_monthly_url", "starter", "starter_monthly_price_id"),
    ("starter_yearly_url", "starter", "starter_yearly_price_id"),
    ("pro_monthly_url", "pro", "pro_monthly_price_id"),
    ("pro_yearly_url", "pro", "pro_yearly_price_id"),
)


def _read_query() -> dict[str, str]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _tag(app_name: str, environment: str, plan: str, price_id: str) -> dict[str, str]:
    return {
        "app": app_name,
        "environment": environment,
        "plan": plan,
        "zoomify_plan": plan,
        "zoomify_price_id": price_id,
    }


def _metadata(link) -> dict[str, str]:
    if hasattr(link, "to_dict"):
        return dict(link.to_dict().get("metadata") or {})
    raw = getattr(link, "metadata", None) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _find_link(app_name: str, environment: str, plan: str, price_id: str):
    for link in stripe.PaymentLink.list(active=True, limit=100).auto_paging_iter():
        meta = _metadata(link)
        if (
            meta.get("app") == app_name
            and meta.get("environment") == environment
            and meta.get("plan") == plan
            and meta.get("zoomify_price_id") == price_id
        ):
            return link
    return None


def _create_link(*, app_name: str, environment: str, plan: str, price_id: str):
    return stripe.PaymentLink.create(
        line_items=[{"price": price_id, "quantity": 1}],
        metadata=_tag(app_name, environment, plan, price_id),
        subscription_data={"metadata": {"plan": plan}},
    )


def main() -> None:
    query = _read_query()
    api_key = (query.get("stripe_api_key") or os.environ.get("STRIPE_API_KEY", "")).strip()
    if not api_key:
        print(
            json.dumps(
                {
                    "error": "Stripe API key required (query stripe_api_key or STRIPE_API_KEY env)"
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    stripe.api_key = api_key
    app_name = query.get("app_name", "zoomify")
    environment = query.get("environment", "dev")

    result: dict[str, str] = {}
    for out_key, plan, price_field in LINK_SPECS:
        price_id = query.get(price_field, "")
        if not price_id:
            print(json.dumps({"error": f"Missing {price_field} in query"}), file=sys.stderr)
            sys.exit(1)

        link = _find_link(app_name, environment, plan, price_id)
        if link is None:
            link = _create_link(
                app_name=app_name,
                environment=environment,
                plan=plan,
                price_id=price_id,
            )
        result[out_key] = link.url

    print(json.dumps(result))


if __name__ == "__main__":
    main()
