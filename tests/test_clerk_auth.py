"""Tests for zoomify.clerk_auth — Clerk JWT verification."""

from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from zoomify import clerk_auth


@pytest.fixture(autouse=True)
def _clear_jwks_cache(monkeypatch):
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    clerk_auth.reset_jwks_cache()
    yield
    clerk_auth.reset_jwks_cache()


def test_auth_disabled_by_default():
    assert not clerk_auth.is_clerk_enabled()


def test_auth_enabled_when_jwks_configured(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/.well-known/jwks.json")
    assert clerk_auth.is_clerk_enabled()


def test_require_clerk_user_bypasses_when_disabled():
    import asyncio

    user = asyncio.run(clerk_auth.require_clerk_user(None))
    assert user["bypass"] is True


def test_require_clerk_user_rejects_missing_token(monkeypatch):
    import asyncio

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/.well-known/jwks.json")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(clerk_auth.require_clerk_user(None))
    assert exc.value.status_code == 401


def test_verify_clerk_token_with_mock_jwks(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    class FakeSigningKey:
        key = pem

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, _token):
            return FakeSigningKey()

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/.well-known/jwks.json")
    monkeypatch.setattr(clerk_auth, "_jwks_client", lambda: FakeJWKClient())

    token = jwt.encode({"sub": "user_123"}, private_key, algorithm="RS256")
    claims = clerk_auth.verify_clerk_token(token)
    assert claims["sub"] == "user_123"
