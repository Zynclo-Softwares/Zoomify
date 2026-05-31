"""Fetch vision + tool-calling + structured-output models from OpenRouter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import OPENROUTER_BASE_URL, DEFAULT_MODEL

# Used when the models API is unreachable or no key is configured yet.
FALLBACK_VISION_MODELS: tuple[str, ...] = (
    "anthropic/claude-opus-4.8-fast",
    "google/gemini-2.5-flash",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4",
)

_CACHE: list[str] | None = None


def _is_eligible_model(entry: dict) -> bool:
    """Vision input, text output, tool calling, and strict structured JSON."""
    arch = entry.get("architecture") or {}
    inputs = arch.get("input_modalities") or []
    outputs = arch.get("output_modalities") or []
    params = entry.get("supported_parameters") or []
    return (
        "image" in inputs
        and "text" in outputs
        and "tools" in params
        and "structured_outputs" in params
    )


def _http_get_json(url: str, api_key: str | None = None) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_openrouter_health(*, api_key: str) -> dict:
    """Verify an OpenRouter API key against OpenRouter's auth endpoint."""
    base = OPENROUTER_BASE_URL.rstrip("/")
    url = f"{base}/auth/key"
    try:
        _http_get_json(url, api_key)
        return {"ok": True}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {"ok": False, "detail": "Invalid OpenRouter API key"}
        return {"ok": False, "detail": f"OpenRouter returned HTTP {exc.code}"}
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        KeyError,
    ):
        return {"ok": False, "detail": "OpenRouter unreachable"}


def fetch_vision_models(*, api_key: str | None = None, force_refresh: bool = False) -> list[str]:
    """Return OpenRouter model IDs for vision, tools, and structured JSON output."""
    global _CACHE
    if _CACHE is not None and not force_refresh:
        return list(_CACHE)

    base = OPENROUTER_BASE_URL.rstrip("/")
    query = "output_modalities=all&supported_parameters=tools"
    urls = (
        [f"{base}/models/user?{query}", f"{base}/models?{query}"]
        if api_key
        else [f"{base}/models?{query}"]
    )

    last_error: Exception | None = None
    for url in urls:
        try:
            payload = _http_get_json(url, api_key)
            ids = sorted(
                m["id"] for m in payload.get("data", []) if m.get("id") and _is_eligible_model(m)
            )
            if ids:
                _CACHE = ids
                return list(ids)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            KeyError,
        ) as e:
            last_error = e
            continue

    _CACHE = list(FALLBACK_VISION_MODELS)
    if last_error is not None:
        return list(_CACHE)
    return list(_CACHE)


def resolve_model(selected: str | None, choices: list[str] | None = None) -> str:
    """Pick a valid model id from the dropdown selection."""
    if selected and (not choices or selected in choices):
        return selected
    if choices:
        if DEFAULT_MODEL in choices:
            return DEFAULT_MODEL
        return choices[0]
    return DEFAULT_MODEL


def model_dropdown_update(*, api_key: str | None = None, force_refresh: bool = False) -> dict:
    """Build a Gradio ``Dropdown`` update dict with choices + default value."""
    choices = fetch_vision_models(api_key=api_key, force_refresh=force_refresh)
    return {"choices": choices, "value": resolve_model(DEFAULT_MODEL, choices)}


def reset_cache() -> None:
    """Clear the in-memory model list (for tests)."""
    global _CACHE
    _CACHE = None
