"""Tests for the Zoomify MCP server — tools, metering, auth, and the HTTP transport."""

from __future__ import annotations

import asyncio
import base64
import io

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from PIL import Image

from zoomify import mcp_server
from zoomify.db import increment_monthly_usage, user_billing_status
from zoomify.images import uploads
from zoomify.plans import PLANS
from zoomify.platform_keys import create_platform_key
from zoomify.session import store

USER = mcp_server.DEV_USER_ID


def call(server, name: str, args: dict | None = None):
    return asyncio.run(server.call_tool(name, args or {}))


def text_of(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


def image_of(result) -> Image.Image:
    block = next(c for c in result.content if c.type == "image")
    return Image.open(io.BytesIO(base64.b64decode(block.data)))


def session_id_of(result) -> str:
    return text_of(result).split("session_id ")[1].split(".")[0]


@pytest.fixture
def server():
    return mcp_server.build_mcp()


@pytest.fixture
def image_id(small_png_bytes):
    return uploads.put(USER, small_png_bytes, "plan.png", "image", 1).id


@pytest.fixture
def opened(server, image_id):
    return session_id_of(call(server, "open_image", {"image_id": image_id}))


# --------------------------------------------------------------- catalog


def test_tool_catalog_matches_registered_tools(server):
    tools = asyncio.run(server.list_tools())
    names = [t.name for t in tools]
    assert names == [t["name"] for t in mcp_server.tools_catalog()]
    assert all(t.description for t in tools)
    zoom = next(t for t in tools if t.name == "zoom")
    assert set(zoom.input_schema["required"]) == {"session_id", "select"}
    assert "ctx" not in zoom.input_schema["properties"]


def test_instructions_mention_workflow_and_skills(server):
    assert "open_image" in server.instructions
    assert "zoom-basics" in server.instructions


def test_skills_exposed_as_resources_and_prompts(server):
    resources = asyncio.run(server.list_resources())
    assert "zoomify://skills/zoom-basics" in [str(r.uri) for r in resources]
    prompts = [p.name for p in asyncio.run(server.list_prompts())]
    assert {"zoom-basics", "engineering-drawings", "inspect-image"} <= set(prompts)

    prompt = asyncio.run(
        server.get_prompt("inspect-image", {"image": "img_abc", "task": "Read the title block"})
    )
    body = prompt.messages[0].content.text
    assert "image_id" in body and "Read the title block" in body


def test_read_skill(server):
    assert text_of(call(server, "read_skill")).startswith("# Zoom basics")
    assert "title block" in text_of(call(server, "read_skill", {"name": "engineering-drawings"}))
    with pytest.raises(ToolError, match="Unknown skill"):
        call(server, "read_skill", {"name": "nope"})


# --------------------------------------------------------------- open_image


def test_open_image_from_upload(server, image_id):
    result = call(server, "open_image", {"image_id": image_id})
    text = text_of(result)
    assert "Opened 'plan.png' (400x300 px)" in text
    assert "Grid: columns A–" in text
    assert "Requests left this month: 999" in text
    assert image_of(result).size[0] > 400  # gridded view carries a ruler margin
    assert store.count(USER) == 1


def test_open_image_pdf_page(server, pdf_bytes):
    upload = uploads.put(USER, pdf_bytes, "set.pdf", "pdf", 2)
    text = text_of(call(server, "open_image", {"image_id": upload.id, "page": 2}))
    assert "PDF page 2 of 2" in text
    with pytest.raises(ToolError, match="out of range"):
        call(server, "open_image", {"image_id": upload.id, "page": 3})


def test_open_image_from_url(server, small_png_bytes, monkeypatch):
    seen = {}

    def fake_fetch(url, max_bytes):
        seen.update(url=url, max_bytes=max_bytes)
        return small_png_bytes

    monkeypatch.setattr(mcp_server, "fetch_url", fake_fetch)
    text = text_of(call(server, "open_image", {"image_url": "https://example.com/a/site.png"}))
    assert "Opened 'site.png'" in text
    assert seen["max_bytes"] == PLANS["free"].max_image_mb * 1024 * 1024


def test_open_image_requires_exactly_one_source(server, image_id):
    with pytest.raises(ToolError, match="exactly one"):
        call(server, "open_image", {})
    with pytest.raises(ToolError, match="exactly one"):
        call(server, "open_image", {"image_id": image_id, "image_url": "https://x.test/a.png"})


def test_open_image_unknown_upload_is_not_charged(server):
    with pytest.raises(ToolError, match="Unknown or expired image_id"):
        call(server, "open_image", {"image_id": "img_missing"})
    assert user_billing_status(USER)["monthly_used"] == 0


def test_open_image_evicts_oldest_beyond_plan_cap(server, image_id):
    cap = PLANS["free"].max_open_images
    ids = [session_id_of(call(server, "open_image", {"image_id": image_id})) for _ in range(cap)]
    text = text_of(call(server, "open_image", {"image_id": image_id}))
    assert "Closed 1 older session(s)" in text
    assert store.count(USER) == cap
    assert store.get(USER, ids[0]) is None


# --------------------------------------------------------------- zoom & navigation


def test_zoom_then_navigate(server, opened):
    zoomed = call(server, "zoom", {"session_id": opened, "select": "B2", "zoom": 4})
    assert "Zoomed selection 'B2' by 4x" in text_of(zoomed)
    assert image_of(zoomed).size[0] > 0
    assert store.get(USER, opened).state.depth == 1

    assert "Popped" in text_of(call(server, "undo", {"session_id": opened}))
    assert store.get(USER, opened).state.depth == 0
    assert "Redid" in text_of(call(server, "redo", {"session_id": opened}))
    assert "depth 1" in text_of(call(server, "view", {"session_id": opened}))
    assert "back at root" in text_of(call(server, "restore", {"session_id": opened}))
    assert store.get(USER, opened).state.depth == 0


def test_only_open_and_zoom_are_metered(server, opened):
    assert user_billing_status(USER)["monthly_used"] == 1
    call(server, "zoom", {"session_id": opened, "select": "A1"})
    assert user_billing_status(USER)["monthly_used"] == 2
    for tool in ("undo", "redo", "restore", "view"):
        call(server, tool, {"session_id": opened})
    call(server, "usage")
    call(server, "read_skill")
    assert user_billing_status(USER)["monthly_used"] == 2


def test_bad_selection_is_an_error_and_not_charged(server, opened):
    with pytest.raises(ToolError, match="column out of range"):
        call(server, "zoom", {"session_id": opened, "select": "ZZ99"})
    assert user_billing_status(USER)["monthly_used"] == 1
    assert store.get(USER, opened).state.depth == 0


def test_unknown_session(server):
    with pytest.raises(ToolError, match="Unknown or expired session"):
        call(server, "zoom", {"session_id": "zs_nope", "select": "A1"})
    with pytest.raises(ToolError, match="Unknown or expired session"):
        call(server, "undo", {"session_id": "zs_nope"})


def test_sessions_are_private_to_their_owner(server, opened):
    assert store.get("someone-else", opened) is None


# --------------------------------------------------------------- metering


def test_monthly_limit_blocks_metered_tools_only(server, opened):
    increment_monthly_usage(USER, PLANS["free"].monthly_limit)
    with pytest.raises(ToolError, match="Monthly request limit reached"):
        call(server, "zoom", {"session_id": opened, "select": "A1"})
    assert "Current view" in text_of(call(server, "view", {"session_id": opened}))


def test_rate_limit_message(server, opened, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_FREE_PER_MINUTE", "1")
    with pytest.raises(ToolError, match="Rate limit exceeded"):
        call(server, "zoom", {"session_id": opened, "select": "A1"})


def test_usage_tool(server, opened):
    data = call(server, "usage").structured_content
    assert data["plan"] == "free"
    assert data["monthly_used"] == 1
    assert data["monthly_remaining"] == PLANS["free"].monthly_limit - 1
    assert data["open_images"] == 1
    assert data["metering"] == "enabled"


def test_quotas_can_be_disabled_for_self_hosting(server, image_id, monkeypatch):
    monkeypatch.setenv("ZOOMIFY_DISABLE_QUOTAS", "true")
    increment_monthly_usage(USER, PLANS["free"].monthly_limit)
    text = text_of(call(server, "open_image", {"image_id": image_id}))
    assert "Opened" in text and "Requests left" not in text
    assert call(server, "usage").structured_content["metering"] == "disabled"


# --------------------------------------------------------------- auth


def test_extract_api_key_sources():
    assert mcp_server.extract_api_key({"authorization": "Bearer zfy_live_abc"}) == "zfy_live_abc"
    assert mcp_server.extract_api_key({"x-api-key": "zfy_live_abc"}) == "zfy_live_abc"
    assert mcp_server.extract_api_key({}, {"api_key": "zfy_live_abc"}) == "zfy_live_abc"
    assert mcp_server.extract_api_key({}, {}) is None


def test_authenticate_dev_bypass_and_keys(monkeypatch):
    from zoomify import clerk_auth

    assert mcp_server.authenticate({})["sub"] == USER

    key = create_platform_key("user_k")["key"]
    assert mcp_server.authenticate({"authorization": f"Bearer {key}"})["sub"] == "user_k"
    with pytest.raises(mcp_server.AuthError, match="revoked"):
        mcp_server.authenticate({"authorization": "Bearer zfy_live_" + "x" * 20})
    with pytest.raises(mcp_server.AuthError, match="zfy_live_"):
        mcp_server.authenticate({"authorization": "Bearer something-else"})

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()
    with pytest.raises(mcp_server.AuthError, match="API key required"):
        mcp_server.authenticate({})


# --------------------------------------------------------------- HTTP transport

MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client, method: str, params: dict | None = None, headers: dict | None = None, path="/mcp"):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post(path, json=body, headers={**MCP_HEADERS, **(headers or {})})


INIT = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "pytest", "version": "0"},
}


def test_http_initialize_and_list_tools(live_client):
    r = rpc(live_client, "initialize", INIT)
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["serverInfo"]["name"] == "zoomify"
    assert "open_image" in result["instructions"]

    r = rpc(live_client, "tools/list")
    assert r.status_code == 200
    assert [t["name"] for t in r.json()["result"]["tools"]][:2] == ["open_image", "zoom"]


def test_http_tool_call_roundtrip(live_client, small_png_bytes):
    up = live_client.post(
        "/api/images", files={"file": ("plan.png", small_png_bytes, "image/png")}
    ).json()
    r = rpc(
        live_client,
        "tools/call",
        {"name": "open_image", "arguments": {"image_id": up["image_id"]}},
    )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result.get("isError") in (None, False)
    assert [c["type"] for c in result["content"]] == ["text", "image"]
    assert result["content"][1]["mimeType"] == "image/png"

    r = rpc(
        live_client,
        "tools/call",
        {"name": "zoom", "arguments": {"session_id": "zs_x", "select": "A1"}},
    )
    assert r.json()["result"]["isError"] is True


def test_http_requires_key_when_clerk_enabled(live_client, monkeypatch):
    from zoomify import clerk_auth

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()

    r = rpc(live_client, "tools/list")
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")
    assert "API key required" in r.json()["message"]

    r = rpc(live_client, "tools/list", headers={"Authorization": "Bearer zfy_live_" + "0" * 24})
    assert r.status_code == 401

    key = create_platform_key("user_http")["key"]
    r = rpc(
        live_client,
        "tools/call",
        {"name": "usage", "arguments": {}},
        {"Authorization": f"Bearer {key}"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["structuredContent"]["plan"] == "free"

    # Clients that cannot send headers may pass the key in the URL.
    r = rpc(live_client, "tools/list", path=f"/mcp?api_key={key}")
    assert r.status_code == 200


def test_http_usage_is_attributed_to_the_key_owner(live_client, small_png_bytes, monkeypatch):
    from zoomify import clerk_auth

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()
    key = create_platform_key("user_meter")["key"]
    auth = {"Authorization": f"Bearer {key}"}

    up = live_client.post(
        "/api/images", files={"file": ("plan.png", small_png_bytes, "image/png")}, headers=auth
    ).json()
    r = rpc(
        live_client,
        "tools/call",
        {"name": "open_image", "arguments": {"image_id": up["image_id"]}},
        auth,
    )
    assert r.json()["result"].get("isError") in (None, False)
    assert user_billing_status("user_meter")["monthly_used"] == 1
    assert user_billing_status(USER)["monthly_used"] == 0
