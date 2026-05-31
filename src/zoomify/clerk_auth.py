"""Clerk session JWT verification for protected API routes."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from zoomify.platform_keys import is_platform_key, lookup_clerk_user_by_platform_key

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
    user = await require_user(creds)
    if user.get("auth") == "platform_key":
        raise HTTPException(
            status_code=403,
            detail="Clerk session required for this endpoint",
        )
    return user


async def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """Accept either auth method; both resolve to the same Clerk ``sub`` user id.

    - Clerk session JWT (browser / short-lived)
    - Zoomify platform API key ``zfy_live_...`` (programmatic / long-lived)
    """
    if not is_clerk_enabled():
        return {"sub": "dev-local", "bypass": True}

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")

    token = creds.credentials.strip()
    if is_platform_key(token):
        clerk_id = lookup_clerk_user_by_platform_key(token)
        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        return {"sub": clerk_id, "auth": "platform_key"}

    try:
        claims = verify_clerk_token(token)
        claims["auth"] = "clerk"
        return claims
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Authentication failed") from exc
