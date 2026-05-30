"""Bring-your-own-key encryption (RSA-OAEP) for OpenRouter API keys."""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

_log = logging.getLogger(__name__)

HEADER_NAME = "X-Encrypted-Api-Key"
_dev_keypair: tuple[str, str] | None = None


def generate_keypair_pem() -> tuple[str, str]:
    """Return (private_pem, public_pem) for BYOK configuration."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _load_private_key() -> RSAPrivateKey:
    pem = os.environ.get("BYOK_PRIVATE_KEY", "").strip()
    if not pem:
        global _dev_keypair
        if _dev_keypair is None:
            _dev_keypair = generate_keypair_pem()
            _log.warning(
                "BYOK_PRIVATE_KEY is not set; using ephemeral dev keys "
                "(saved client keys stop working after server restart)"
            )
        pem = _dev_keypair[0]
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise TypeError("BYOK_PRIVATE_KEY must be an RSA private key")
    return key


def _load_public_key() -> RSAPublicKey:
    pem = os.environ.get("BYOK_PUBLIC_KEY", "").strip()
    if pem:
        key = serialization.load_pem_public_key(pem.encode())
        if not isinstance(key, RSAPublicKey):
            raise TypeError("BYOK_PUBLIC_KEY must be an RSA public key")
        return key
    return _load_private_key().public_key()


def is_byok_ready() -> bool:
    """True when the server can decrypt BYOK payloads."""
    try:
        _load_public_key()
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def public_key_pem() -> str:
    return (
        _load_public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


def reset_byok_cache() -> None:
    """Clear cached keys (for tests)."""
    global _dev_keypair
    _dev_keypair = None
    if hasattr(public_key_pem, "cache_clear"):
        public_key_pem.cache_clear()


def encrypt_api_key(plaintext: str, *, public_pem: str | None = None) -> str:
    """Encrypt a plaintext API key (for tests and tooling)."""
    pem = public_pem or public_key_pem()
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, RSAPublicKey):
        raise TypeError("Public key must be RSA")
    ciphertext = key.encrypt(
        plaintext.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(ciphertext).decode("ascii")


def decrypt_api_key(ciphertext_b64: str) -> str:
    """Decrypt a BYOK payload from the client request header."""
    ciphertext = base64.b64decode(ciphertext_b64, validate=True)
    plaintext = _load_private_key().decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plaintext.decode("utf-8")
