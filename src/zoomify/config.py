"""LLM provider configuration (OpenRouter — keys supplied per request via BYOK)."""

from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = "anthropic/claude-opus-4.8-fast"
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1",
)


def make_client(api_key: str) -> OpenAI:
    """Build an OpenAI-compatible client for OpenRouter."""
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)
