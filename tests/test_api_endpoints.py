"""Additional HTTP coverage for FastAPI routes."""

from __future__ import annotations

import json

import pytest

from zoomify import byok_crypto
from zoomify.db import get_user, reset_memory_store


@pytest.fixture(autouse=True)
def _billing_memory():
    from zoomify.platform_keys import reset_platform_key_store

    reset_memory_store()
    reset_platform_key_store()
    yield
    reset_memory_store()
    reset_platform_key_store()


def test_health_extended_fields(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["mongodb_enabled"] is False
    assert data["stripe_webhook_configured"] is False


def test_byok_public_key(client, byok_headers):
    r = client.get("/api/byok/public-key")
    assert r.status_code == 200
    assert "BEGIN PUBLIC KEY" in r.json()["public_key_pem"]


def test_byok_public_key_unavailable(client, monkeypatch):
    monkeypatch.setattr("server.is_byok_ready", lambda: False)
    r = client.get("/api/byok/public-key")
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


def test_auth_me_dev_bypass(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == "dev-local"
    assert data["bypass"] is True


def test_models_rejects_invalid_encrypted_key(client, monkeypatch):
    monkeypatch.delenv("BYOK_PRIVATE_KEY", raising=False)
    byok_crypto.reset_byok_cache()
    private_pem, public_pem = byok_crypto.generate_keypair_pem()
    monkeypatch.setenv("BYOK_PRIVATE_KEY", private_pem)
    byok_crypto.reset_byok_cache()
    bad = byok_crypto.encrypt_api_key("sk-or-test", public_pem=public_pem)[:-5] + "xxxxx"

    r = client.get("/api/models", headers={byok_crypto.HEADER_NAME: bad})
    assert r.status_code == 400
    assert "invalid" in r.json()["detail"].lower()


def test_delete_session(client):
    r = client.delete("/api/session/session-abc")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_openapi_and_redoc(client):
    openapi = client.get("/api/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/query" in paths
    assert "/api/billing/plans" in paths

    redoc = client.get("/api/redoc")
    assert redoc.status_code == 200


def test_billing_plans_structure(client):
    r = client.get("/api/billing/plans")
    assert r.status_code == 200
    data = r.json()
    plan_ids = {p["id"] for p in data["plans"]}
    assert plan_ids == {"free", "starter", "pro"}
    assert data["premium_schema"]["name"]


def test_billing_status_after_usage(client, monkeypatch, byok_headers):
    monkeypatch.setattr(
        "server.run_query_stream",
        lambda **_: iter([{"type": "assistant", "content": "ok"}]),
    )
    client.post("/api/query", data={"query": "hello"}, headers=byok_headers)
    r = client.get("/api/billing/status")
    assert r.status_code == 200
    assert r.json()["daily_used"] == 1
    assert r.json()["daily_remaining"] == r.json()["daily_limit"] - 1


def test_query_quota_message(client, monkeypatch, byok_headers):
    monkeypatch.setattr("zoomify.billing._check_rate_limit", lambda *_: None)
    monkeypatch.setattr(
        "server.run_query_stream",
        lambda **_: iter([{"type": "assistant", "content": "ok"}]),
    )
    from zoomify.plans import PLANS

    for _ in range(PLANS["free"].daily_limit):
        client.post("/api/query", data={"query": "x"}, headers=byok_headers)

    r = client.post("/api/query", data={"query": "x"}, headers=byok_headers)
    assert r.status_code == 429
    assert "daily limit" in r.json()["detail"].lower()


def test_billing_webhook_subscription_deleted(client):
    upsert = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "user_del",
                "subscription": "sub_del",
                "customer": "cus_del",
                "metadata": {"plan": "starter"},
            }
        },
    }
    client.post("/api/billing/webhook", json=upsert)

    payload = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_del",
                "metadata": {"clerk_user_id": "user_del"},
                "status": "canceled",
            }
        },
    }
    r = client.post("/api/billing/webhook", json=payload)
    assert r.status_code == 200
    user = get_user("user_del")
    assert user["plan"] == "free"
    assert user["subscriptionStatus"] == "canceled"


def test_billing_webhook_invalid_payload(client):
    r = client.post(
        "/api/billing/webhook",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_query_stream_error_event(client, small_png_bytes, monkeypatch, byok_headers):
    def fake_run(**kwargs):
        yield {"type": "session", "session_id": "s-err"}
        yield {"type": "error", "message": "Agent failed"}

    monkeypatch.setattr("server.run_query_stream", fake_run)
    r = client.post(
        "/api/query",
        data={"query": "x"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
        headers=byok_headers,
    )
    assert r.status_code == 200
    lines = [json.loads(ln) for ln in r.text.strip().split("\n") if ln]
    assert lines[-1]["type"] == "error"
