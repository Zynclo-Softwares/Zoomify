"""Zoomify platform API keys — one long-lived key per Clerk user for programmatic access."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

KEY_PREFIX = "zfy_live_"
PLATFORM_API_KEYS = "platform_api_keys"

_memory_keys: dict[str, dict[str, Any]] = {}
_memory_by_hash: dict[str, str] = {}


def is_platform_key(token: str) -> bool:
    return token.startswith(KEY_PREFIX)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _display_prefix(key: str) -> str:
    return key[:16]


def _keys_col():
    from zoomify.db import _get_client, mongodb_database_name, mongodb_enabled

    if not mongodb_enabled():
        return None
    client = _get_client()
    if client is None:
        return None
    return client[mongodb_database_name()][PLATFORM_API_KEYS]


def ensure_platform_key_indexes() -> None:
    col = _keys_col()
    if col is not None:
        col.create_index("clerkUserId", unique=True)
        col.create_index("keyHash", unique=True)


def reset_platform_key_store() -> None:
    """Clear in-memory platform keys (tests)."""
    _memory_keys.clear()
    _memory_by_hash.clear()


def lookup_clerk_user_by_platform_key(key: str) -> str | None:
    if not is_platform_key(key) or len(key) < len(KEY_PREFIX) + 8:
        return None
    key_hash = _hash_key(key)
    col = _keys_col()
    if col is not None:
        doc = col.find_one({"keyHash": key_hash})
        if doc:
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"lastUsedAt": datetime.now(UTC)}},
            )
            return str(doc["clerkUserId"])
        return None

    clerk_id = _memory_by_hash.get(key_hash)
    if clerk_id and clerk_id in _memory_keys:
        _memory_keys[clerk_id]["lastUsedAt"] = datetime.now(UTC)
        return clerk_id
    return None


def platform_key_status(clerk_user_id: str) -> dict[str, Any]:
    col = _keys_col()
    if col is not None:
        doc = col.find_one({"clerkUserId": clerk_user_id})
        if not doc:
            return {"has_key": False, "prefix": None, "created_at": None}
        created = doc.get("createdAt")
        return {
            "has_key": True,
            "prefix": doc.get("prefix"),
            "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
        }

    doc = _memory_keys.get(clerk_user_id)
    if not doc:
        return {"has_key": False, "prefix": None, "created_at": None}
    return {
        "has_key": True,
        "prefix": doc.get("prefix"),
        "created_at": doc.get("createdAt"),
    }


def _store_key(clerk_user_id: str, key: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    record = {
        "clerkUserId": clerk_user_id,
        "keyHash": _hash_key(key),
        "prefix": _display_prefix(key),
        "createdAt": now,
        "lastUsedAt": None,
    }
    col = _keys_col()
    if col is not None:
        col.replace_one({"clerkUserId": clerk_user_id}, record, upsert=True)
    else:
        old = _memory_keys.get(clerk_user_id)
        if old:
            _memory_by_hash.pop(old["keyHash"], None)
        _memory_keys[clerk_user_id] = record
        _memory_by_hash[record["keyHash"]] = clerk_user_id

    return {
        "key": key,
        "prefix": record["prefix"],
        "created_at": now.isoformat(),
    }


def create_platform_key(clerk_user_id: str) -> dict[str, Any]:
    status = platform_key_status(clerk_user_id)
    if status["has_key"]:
        raise ValueError("Platform API key already exists")
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return _store_key(clerk_user_id, key)


def rotate_platform_key(clerk_user_id: str) -> dict[str, Any]:
    status = platform_key_status(clerk_user_id)
    if not status["has_key"]:
        raise ValueError("No platform API key to rotate")
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return _store_key(clerk_user_id, key)
