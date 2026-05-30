"""Tests for zoomify.openrouter_models — OpenRouter vision model picker."""

from __future__ import annotations

import json

import pytest

from zoomify.openrouter_models import (
    DEFAULT_MODEL,
    FALLBACK_VISION_MODELS,
    fetch_vision_models,
    model_dropdown_update,
    reset_cache,
    resolve_model,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


def test_fetch_vision_models_filters_image_and_tools(monkeypatch):
    payload = {
        "data": [
            {
                "id": "good/model",
                "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
                "supported_parameters": ["tools", "temperature"],
            },
            {
                "id": "text-only/model",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "supported_parameters": ["tools"],
            },
            {
                "id": "no-tools/model",
                "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
                "supported_parameters": ["temperature"],
            },
        ]
    }

    def fake_get(url, api_key=None):
        assert "supported_parameters=tools" in url
        return payload

    monkeypatch.setattr("zoomify.openrouter_models._http_get_json", fake_get)
    ids = fetch_vision_models()
    assert ids == ["good/model"]


def test_fetch_vision_models_uses_fallback_on_error(monkeypatch):
    def boom(*_a, **_k):
        raise TimeoutError("offline")

    monkeypatch.setattr("zoomify.openrouter_models._http_get_json", boom)
    ids = fetch_vision_models()
    assert ids == list(FALLBACK_VISION_MODELS)


def test_fetch_vision_models_caches_until_refresh(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, api_key=None):
        calls["n"] += 1
        return {"data": [{
            "id": "cached/model",
            "architecture": {"input_modalities": ["image", "text"], "output_modalities": ["text"]},
            "supported_parameters": ["tools"],
        }]}

    monkeypatch.setattr("zoomify.openrouter_models._http_get_json", fake_get)
    assert fetch_vision_models() == ["cached/model"]
    assert fetch_vision_models() == ["cached/model"]
    assert calls["n"] == 1
    assert fetch_vision_models(force_refresh=True) == ["cached/model"]
    assert calls["n"] == 2


def test_resolve_model_prefers_default_when_present():
    choices = ["alpha/model", DEFAULT_MODEL, "zeta/model"]
    assert resolve_model(None, choices) == DEFAULT_MODEL
    assert resolve_model("alpha/model", choices) == "alpha/model"


def test_model_dropdown_update_shape(monkeypatch):
    monkeypatch.setattr(
        "zoomify.openrouter_models.fetch_vision_models",
        lambda **_: ["alpha/model", DEFAULT_MODEL],
    )
    upd = model_dropdown_update()
    assert upd["choices"] == ["alpha/model", DEFAULT_MODEL]
    assert upd["value"] == DEFAULT_MODEL
