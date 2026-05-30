"""LLM provider configuration (OpenRouter by default)."""

from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = (
    os.environ.get("LLM_MODEL")
    or os.environ.get("OPENAI_MODEL")
    or "google/gemini-3.1-flash-lite"
)
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1",
)


def api_key() -> str | None:
    """Return the configured API key, preferring OpenRouter."""
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")


def has_api_key() -> bool:
    return bool(api_key())


def make_client() -> OpenAI:
    """Build an OpenAI-compatible client (OpenRouter or direct OpenAI)."""
    key = api_key() or ""
    if os.environ.get("OPENROUTER_API_KEY"):
        return OpenAI(api_key=key, base_url=OPENROUTER_BASE_URL)
    return OpenAI(api_key=key)
