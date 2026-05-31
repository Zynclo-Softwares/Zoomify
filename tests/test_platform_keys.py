"""Tests for Zoomify platform API keys."""

from __future__ import annotations

import asyncio

import pytest

from zoomify import clerk_auth, platform_keys
from zoomify.platform_keys import KEY_PREFIX, create_platform_key, rotate_platform_key


@pytest.fixture(autouse=True)
def _clean_keys():
    platform_keys.reset_platform_key_store()
    yield
    platform_keys.reset_platform_key_store()


def test_create_and_lookup_platform_key():
    created = create_platform_key("user_1")
    assert created["key"].startswith(KEY_PREFIX)
    assert created["prefix"] == created["key"][:16]

    status = platform_keys.platform_key_status("user_1")
    assert status["has_key"] is True
    assert status["prefix"] == created["prefix"]

    clerk_id = platform_keys.lookup_clerk_user_by_platform_key(created["key"])
    assert clerk_id == "user_1"


def test_create_rejects_second_key():
    create_platform_key("user_1")
    with pytest.raises(ValueError, match="already exists"):
        create_platform_key("user_1")


def test_rotate_replaces_key():
    first = create_platform_key("user_1")
    rotated = rotate_platform_key("user_1")
    assert rotated["key"] != first["key"]
    assert platform_keys.lookup_clerk_user_by_platform_key(first["key"]) is None
    assert platform_keys.lookup_clerk_user_by_platform_key(rotated["key"]) == "user_1"


def test_rotate_requires_existing_key():
    with pytest.raises(ValueError, match="No platform API key"):
        rotate_platform_key("user_none")


def test_require_user_accepts_platform_key(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()
    created = create_platform_key("user_api")
    creds = type("C", (), {"scheme": "Bearer", "credentials": created["key"]})()

    user = asyncio.run(clerk_auth.require_user(creds))
    assert user["sub"] == "user_api"
    assert user["auth"] == "platform_key"


def test_require_clerk_user_rejects_platform_key(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()
    created = create_platform_key("user_api")
    creds = type("C", (), {"scheme": "Bearer", "credentials": created["key"]})()

    with pytest.raises(Exception) as exc:
        asyncio.run(clerk_auth.require_clerk_user(creds))
    assert exc.value.status_code == 403


def test_platform_key_http_flow(client, monkeypatch):
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    clerk_auth.reset_jwks_cache()
    r = client.get("/api/platform-key")
    assert r.status_code == 200
    assert r.json()["has_key"] is False

    r = client.post("/api/platform-key")
    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith(KEY_PREFIX)

    r = client.get("/api/platform-key")
    assert r.json()["has_key"] is True
    assert r.json()["prefix"] == body["prefix"]
    assert "key" not in r.json()

    r = client.post("/api/platform-key")
    assert r.status_code == 409

    r = client.post("/api/platform-key/rotate")
    assert r.status_code == 200
    new_key = r.json()["key"]
    assert new_key != body["key"]
    assert platform_keys.lookup_clerk_user_by_platform_key(body["key"]) is None
    assert platform_keys.lookup_clerk_user_by_platform_key(new_key) == "dev-local"
