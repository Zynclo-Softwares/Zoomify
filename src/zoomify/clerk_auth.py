"""Clerk session JWT verification for protected API routes."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

_bearer = HTTPBearer(auto_error=False)


def clerk_jwks_url() -> str | None:
    url = os.environ.get("CLERK_JWKS_URL", "").strip()
    return url or None


def is_clerk_enabled() -> bool:
    """Auth is enforced when JWKS URL is configured."""
    return bool(clerk_jwks_url())


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    url = clerk_jwks_url()
    if not url:
        return None
    return PyJWKClient(url)


def reset_jwks_cache() -> None:
    """Clear cached JWKS client (for tests)."""
    if hasattr(_jwks_client, "cache_clear"):
        _jwks_client.cache_clear()


def verify_clerk_token(token: str) -> dict[str, Any]:
    """Validate a Clerk session JWT and return its claims."""
    client = _jwks_client()
    if client is None:
        raise RuntimeError("CLERK_JWKS_URL is not configured")

    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )


async def require_clerk_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """FastAPI dependency — require a valid Clerk session when auth is enabled."""
    if not is_clerk_enabled():
        return {"sub": "dev-local", "bypass": True}

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        return verify_clerk_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Authentication failed") from exc
