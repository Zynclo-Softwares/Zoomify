import pytest

from zoomify.schema_registry import (
    METADATA_KEY,
    resolve_schema,
    validate_schema_id,
)
from zoomify.trail import render_trail


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "byok_ready" in r.json()
    assert "clerk_enabled" in r.json()


def test_models_endpoint(client, monkeypatch, byok_headers):
    monkeypatch.setattr(
        "server.model_dropdown_update",
        lambda **_: {"choices": ["alpha/model"], "value": "alpha/model"},
    )
    r = client.get("/api/models", headers=byok_headers)
    assert r.status_code == 200
    assert r.json()["choices"] == ["alpha/model"]


def test_models_requires_encrypted_key(client):
    r = client.get("/api/models")
    assert r.status_code == 401


def test_validate_schema_id():
    assert validate_schema_id("acme-sld-v1")
    assert not validate_schema_id("unknown-schema")
    assert not validate_schema_id("")


def test_resolve_schema_param():
    res = resolve_schema(schema_param="acme-sld-v1", image=None, structured=True)
    assert res.schema_id == "acme-sld-v1"
    assert res.source == "param"


def test_resolve_schema_structured_false_ignores_param():
    res = resolve_schema(schema_param="acme-sld-v1", image=None, structured=False)
    assert not res.structured
    assert res.schema_id is None


def test_resolve_schema_invalid_raises():
    with pytest.raises(ValueError, match="Unknown"):
        resolve_schema(schema_param="nope", image=None, structured=True)


def test_metadata_key_constant():
    assert METADATA_KEY == "structure-zoomify"


def test_render_trail_empty():
    assert "Upload an image" in render_trail(None)


def test_query_requires_key(client, small_png_bytes):
    r = client.post(
        "/api/query",
        data={"query": "read it"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
    )
    assert r.status_code == 401


def test_query_stream_session_line(client, small_png_bytes, monkeypatch, byok_headers):
    def fake_run(**kwargs):
        yield {"type": "session", "session_id": "s1"}
        yield {"type": "assistant", "content": "hello"}

    monkeypatch.setattr("server.run_query_stream", fake_run)

    r = client.post(
        "/api/query",
        data={"query": "what?", "model": "alpha/model"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
        headers=byok_headers,
    )
    assert r.status_code == 200
    lines = [ln for ln in r.text.strip().split("\n") if ln]
    assert any('"type": "session"' in ln for ln in lines)
    assert any('"type": "assistant"' in ln for ln in lines)


def test_query_invalid_schema(client, small_png_bytes, byok_headers):
    r = client.post(
        "/api/query",
        data={"query": "x", "schema": "bad-schema"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
        headers=byok_headers,
    )
    assert "Unknown or invalid schema" in r.text
