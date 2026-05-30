import pytest

from zoomify.db import reset_memory_store, upsert_user
from zoomify.plans import PLANS


@pytest.fixture(autouse=True)
def clear_billing_memory():
    reset_memory_store()
    yield
    reset_memory_store()


def test_billing_plans_public(client):
    r = client.get("/api/billing/plans")
    assert r.status_code == 200
    data = r.json()
    assert len(data["plans"]) == 3
    assert data["metered_endpoint"] == "POST /api/query"
    assert "premium_schema" in data


def test_billing_status_default(client):
    r = client.get("/api/billing/status")
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "free"
    assert data["daily_limit"] == PLANS["free"].daily_limit
    assert data["daily_used"] == 0


def test_query_increments_usage(client, small_png_bytes, monkeypatch, byok_headers):
    monkeypatch.setattr(
        "server.run_query_stream",
        lambda **_: iter([{"type": "assistant", "content": "ok"}]),
    )
    r = client.post(
        "/api/query",
        data={"query": "x"},
        headers=byok_headers,
    )
    assert r.status_code == 200
    status = client.get("/api/billing/status").json()
    assert status["daily_used"] == 1


def test_query_quota_blocks(client, small_png_bytes, monkeypatch, byok_headers):
    monkeypatch.setattr("zoomify.billing._check_rate_limit", lambda *_: None)
    monkeypatch.setattr(
        "server.run_query_stream",
        lambda **_: iter([{"type": "assistant", "content": "ok"}]),
    )
    limit = PLANS["free"].daily_limit
    for _ in range(limit):
        r = client.post("/api/query", data={"query": "x"}, headers=byok_headers)
        assert r.status_code == 200

    r = client.post("/api/query", data={"query": "x"}, headers=byok_headers)
    assert r.status_code == 429


def test_starter_plan_higher_limit(client, monkeypatch, byok_headers):
    monkeypatch.setattr("zoomify.billing._check_rate_limit", lambda *_: None)
    monkeypatch.setattr(
        "server.run_query_stream",
        lambda **_: iter([{"type": "assistant", "content": "ok"}]),
    )
    upsert_user("dev-local", plan="starter", subscriptionStatus="active")
    from zoomify.db import increment_daily_usage

    for _ in range(PLANS["free"].daily_limit):
        increment_daily_usage("dev-local")

    r = client.post("/api/query", data={"query": "x"}, headers=byok_headers)
    assert r.status_code == 200


def test_openapi_docs(client):
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Zoomify API"


def test_mongodb_database_from_env(monkeypatch):
    from zoomify.db import DEFAULT_DB_NAME, mongodb_database_name

    assert mongodb_database_name() == DEFAULT_DB_NAME
    monkeypatch.setenv("MONGODB_DATABASE", "Zoomify-Prod")
    assert mongodb_database_name() == "Zoomify-Prod"


def test_rate_limit_env_override(monkeypatch):
    from zoomify.plans import (
        DEFAULT_RATE_LIMIT_PRO_PER_MINUTE,
        DEFAULT_RATE_LIMIT_STARTER_PER_MINUTE,
        rate_limit_per_minute,
    )

    assert rate_limit_per_minute("free") == 10
    assert rate_limit_per_minute("starter") == DEFAULT_RATE_LIMIT_STARTER_PER_MINUTE
    assert rate_limit_per_minute("pro") == DEFAULT_RATE_LIMIT_PRO_PER_MINUTE

    monkeypatch.setenv("RATE_LIMIT_PRO_PER_MINUTE", "60")
    assert rate_limit_per_minute("pro") == 60

    monkeypatch.setenv("RATE_LIMIT_PRO_PER_MINUTE", "not-a-number")
    assert rate_limit_per_minute("pro") == DEFAULT_RATE_LIMIT_PRO_PER_MINUTE


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
