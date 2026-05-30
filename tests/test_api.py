import pytest
from fastapi.testclient import TestClient
from PIL import Image

import server
from zoomify.schema_registry import (
    METADATA_KEY,
    resolve_schema,
    validate_schema_id,
)
from zoomify.session import store
from zoomify.trail import render_trail


@pytest.fixture
def client():
    store.clear()
    return TestClient(server.app)


@pytest.fixture
def small_png_bytes():
    img = Image.new("RGB", (120, 80), "white")
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_models_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "server.model_dropdown_update",
        lambda **_: {"choices": ["alpha/model"], "value": "alpha/model"},
    )
    r = client.get("/api/models")
    assert r.status_code == 200
    assert r.json()["choices"] == ["alpha/model"]


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


def test_query_requires_key(client, small_png_bytes, monkeypatch):
    monkeypatch.setattr("zoomify.query_runner.has_api_key", lambda: False)
    r = client.post(
        "/api/query",
        data={"query": "read it"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
    )
    body = r.text
    assert "error" in body
    assert "API key" in body


def test_query_stream_session_line(client, small_png_bytes, monkeypatch, scripted_client):
    monkeypatch.setattr("zoomify.query_runner.has_api_key", lambda: True)
    fake = scripted_client([("final", "hello")])
    monkeypatch.setattr("zoomify.query_runner.make_client", lambda: fake)

    r = client.post(
        "/api/query",
        data={"query": "what?", "model": "alpha/model"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
    )
    assert r.status_code == 200
    lines = [ln for ln in r.text.strip().split("\n") if ln]
    assert any('"type": "session"' in ln for ln in lines)
    assert any('"type": "assistant"' in ln for ln in lines)


def test_query_invalid_schema(client, small_png_bytes, monkeypatch):
    monkeypatch.setattr("zoomify.query_runner.has_api_key", lambda: True)
    r = client.post(
        "/api/query",
        data={"query": "x", "schema": "bad-schema"},
        files={"image": ("t.png", small_png_bytes, "image/png")},
    )
    assert "Unknown or invalid schema" in r.text
