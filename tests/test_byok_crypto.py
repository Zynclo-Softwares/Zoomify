"""Tests for zoomify.byok_crypto — BYOK RSA encryption."""

from __future__ import annotations

import pytest

from zoomify import byok_crypto


@pytest.fixture(autouse=True)
def _reset_byok(monkeypatch):
    monkeypatch.delenv("BYOK_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("BYOK_PUBLIC_KEY", raising=False)
    byok_crypto.reset_byok_cache()
    yield
    byok_crypto.reset_byok_cache()


@pytest.fixture
def keypair(monkeypatch):
    private_pem, public_pem = byok_crypto.generate_keypair_pem()
    monkeypatch.setenv("BYOK_PRIVATE_KEY", private_pem)
    byok_crypto.reset_byok_cache()
    return private_pem, public_pem


def test_public_key_endpoint_material(keypair):
    _private, public_pem = keypair
    assert "BEGIN PUBLIC KEY" in byok_crypto.public_key_pem()
    assert byok_crypto.is_byok_ready()


def test_encrypt_decrypt_roundtrip(keypair):
    _private, public_pem = keypair
    encrypted = byok_crypto.encrypt_api_key("sk-or-v1-test-key", public_pem=public_pem)
    assert byok_crypto.decrypt_api_key(encrypted) == "sk-or-v1-test-key"


def test_decrypt_rejects_invalid_payload(keypair):
    with pytest.raises(Exception):
        byok_crypto.decrypt_api_key("not-valid-base64!!!")
