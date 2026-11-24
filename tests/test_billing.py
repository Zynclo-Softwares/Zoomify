import pytest

from zoomify import billing
from zoomify.billing import QuotaExceeded, enforce_quota, record_usage
from zoomify.db import increment_monthly_usage, upsert_user, user_billing_status
from zoomify.plans import PLANS


def test_plan_ladder_is_monotonic():
    free, starter, pro = PLANS["free"], PLANS["starter"], PLANS["pro"]
    assert free.price_monthly_usd == 0
    assert free.monthly_limit < starter.monthly_limit < pro.monthly_limit
    assert free.rate_limit_per_minute < starter.rate_limit_per_minute < pro.rate_limit_per_minute
    assert free.max_image_mb <= starter.max_image_mb <= pro.max_image_mb
    assert starter.price_monthly_usd < pro.price_monthly_usd


def test_billing_plans_public(client):
    r = client.get("/api/billing/plans")
    assert r.status_code == 200
    data = r.json()
    assert [p["id"] for p in data["plans"]] == ["free", "starter", "pro"]
    assert data["metered_tools"] == ["open_image", "zoom"]
    assert data["plans"][0]["monthly_limit"] == PLANS["free"].monthly_limit
    assert data["plans"][1]["price_yearly_usd"] == 102  # $10 x 12 less 15%
    assert "custom_skills" in data


def test_billing_status_default(client):
    r = client.get("/api/billing/status")
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "free"
    assert data["monthly_limit"] == PLANS["free"].monthly_limit
    assert data["monthly_used"] == 0
    assert data["monthly_remaining"] == PLANS["free"].monthly_limit
    assert data["resets_at"].endswith("-01T00:00:00+00:00")


def test_record_usage_counts_requests():
    status = enforce_quota("u1")
    after = record_usage("u1", status)
    assert after["monthly_used"] == 1
    assert after["monthly_remaining"] == PLANS["free"].monthly_limit - 1
    assert user_billing_status("u1")["monthly_used"] == 1


def test_monthly_quota_blocks():
    increment_monthly_usage("u1", PLANS["free"].monthly_limit)
    with pytest.raises(QuotaExceeded) as exc:
        enforce_quota("u1")
    assert exc.value.kind == "monthly"
    assert "Monthly request limit reached" in str(exc.value)


def test_paid_plan_has_higher_limit():
    upsert_user("u1", plan="starter", subscriptionStatus="active")
    increment_monthly_usage("u1", PLANS["free"].monthly_limit)
    assert enforce_quota("u1")["plan"] == "starter"


def test_canceled_subscription_falls_back_to_free():
    upsert_user("u1", plan="pro", subscriptionStatus="canceled")
    assert user_billing_status("u1")["plan"] == "free"


def test_usage_is_tracked_per_period(monkeypatch):
    from zoomify import db

    monkeypatch.setattr(db, "current_period", lambda: "2026-01")
    increment_monthly_usage("u1", 5)
    assert user_billing_status("u1")["monthly_used"] == 5
    monkeypatch.setattr(db, "current_period", lambda: "2026-02")
    assert user_billing_status("u1")["monthly_used"] == 0
    assert db.period_resets_at("2026-12") == "2027-01-01T00:00:00+00:00"


def test_rate_limit_blocks_bursts(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_FREE_PER_MINUTE", "2")
    enforce_quota("u1")
    enforce_quota("u1")
    with pytest.raises(QuotaExceeded) as exc:
        enforce_quota("u1")
    assert exc.value.kind == "rate"
    billing.reset_rate_limits()
    enforce_quota("u1")


def test_rate_limit_env_override(monkeypatch):
    from zoomify.plans import rate_limit_per_minute

    assert rate_limit_per_minute("free") == PLANS["free"].rate_limit_per_minute
    assert rate_limit_per_minute("unknown") == PLANS["free"].rate_limit_per_minute
    monkeypatch.setenv("RATE_LIMIT_PRO_PER_MINUTE", "60")
    assert rate_limit_per_minute("pro") == 60
    monkeypatch.setenv("RATE_LIMIT_PRO_PER_MINUTE", "not-a-number")
    assert rate_limit_per_minute("pro") == PLANS["pro"].rate_limit_per_minute


def test_openapi_docs(client):
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Zoomify API"
    assert "/api/images" in schema["paths"]
    assert "/api/query" not in schema["paths"]


def test_mongodb_database_from_env(monkeypatch):
    from zoomify.db import DEFAULT_DB_NAME, mongodb_database_name

    assert mongodb_database_name() == DEFAULT_DB_NAME
    monkeypatch.setenv("MONGODB_DATABASE", "Zoomify-Prod")
    assert mongodb_database_name() == "Zoomify-Prod"


def test_stripe_webhook_checkout(client):
    payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "user_test123",
                "subscription": "sub_1",
                "customer": "cus_1",
                "metadata": {"plan": "pro"},
            }
        },
    }
    r = client.post("/api/billing/webhook", json=payload)
    assert r.status_code == 200
    from zoomify.db import get_user

    user = get_user("user_test123")
    assert user["plan"] == "pro"
    assert user["subscriptionStatus"] == "active"


def test_stripe_subscription_events_resolve_user_by_customer(client):
    """Payment Link subscriptions carry no user metadata — match on the customer id."""
    client.post(
        "/api/billing/webhook",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": "user_c",
                    "subscription": "sub_c",
                    "customer": "cus_c",
                    "metadata": {"plan": "starter"},
                }
            },
        },
    )
    assert user_billing_status("user_c")["plan"] == "starter"

    r = client.post(
        "/api/billing/webhook",
        json={
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_c", "customer": "cus_c", "status": "canceled"}},
        },
    )
    assert r.status_code == 200
    assert user_billing_status("user_c")["plan"] == "free"
