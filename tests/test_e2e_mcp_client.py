"""End-to-end tests: a real MCP client talking to ``/mcp`` over Streamable HTTP.

Unlike ``test_mcp_server.py`` (tools called in-process, or hand-written
JSON-RPC), these drive the whole app the way an agent does: the official MCP
SDK client connects to ``/mcp`` with an API key, negotiates the protocol, and
calls tools; the file itself is sent to the one-time upload link over plain
HTTP, as the ``curl`` command would. Requests go through the real FastAPI app
(auth, routing, MCP transport, tools, metering) over an in-memory ASGI
transport, so no port is opened.
"""

from __future__ import annotations

import asyncio
import base64
import io
from contextlib import asynccontextmanager

import httpx2
import pytest
from mcp import Client, MCPError
from mcp.client.streamable_http import streamable_http_client
from PIL import Image

from zoomify.account.db import user_billing_status
from zoomify.account.platform_keys import create_platform_key
from zoomify.core.session import store

BASE = "http://zoomify.test"
E2E_USER = "user_e2e"


@pytest.fixture
def api_key(monkeypatch) -> str:
    """Turn sign-in on, as in production, and issue a platform key."""
    from zoomify.account import clerk_auth

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()
    return create_platform_key(E2E_USER)["key"]


@asynccontextmanager
async def connect(api_key: str | None):
    """Yield ``(mcp_client, anonymous_http)`` against a running app.

    ``mcp_client`` sends the API key; ``anonymous_http`` sends no credentials,
    like the shell that runs the upload ``curl`` command.
    """
    from zoomify.api.app import app

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with (
            httpx2.AsyncClient(transport=transport, base_url=BASE, headers=headers) as authed,
            httpx2.AsyncClient(transport=transport, base_url=BASE) as anonymous,
        ):
            mcp_transport = streamable_http_client(f"{BASE}/mcp", http_client=authed)
            async with Client(mcp_transport) as client:
                yield client, anonymous


def text_of(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


def image_of(result) -> Image.Image:
    block = next(c for c in result.content if c.type == "image")
    return Image.open(io.BytesIO(base64.b64decode(block.data)))


def session_id_of(result) -> str:
    return text_of(result).split("session_id ")[1].split(".")[0]


def used() -> int:
    return user_billing_status(E2E_USER)["monthly_used"]


def test_client_discovers_tools_skills_and_instructions(api_key):
    async def scenario():
        async with connect(api_key) as (client, _):
            tools = {t.name for t in (await client.list_tools()).tools}
            assert {"open_image", "zoom", "undo", "pdf_pages", "request_upload"} <= tools
            prompts = {p.name for p in (await client.list_prompts()).prompts}
            assert {"zoom-basics", "long-documents", "inspect-image"} <= prompts
            resources = [str(r.uri) for r in (await client.list_resources()).resources]
            assert "zoomify://skills/long-documents" in resources

            skill = await client.call_tool("read_skill", {"name": "long-documents"})
            assert "pdf_pages" in text_of(skill)

    asyncio.run(scenario())


def test_pdf_upload_once_then_pages_zoom_and_undo(api_key, text_pdf_bytes):
    """The full agent flow for a local multi-page PDF."""

    async def scenario():
        async with connect(api_key) as (client, shell):
            # 1. Ask for an upload link; it must not leak the key.
            ticket = (
                await client.call_tool("request_upload", {"file_path": "/work/set.pdf"})
            ).structured_content
            assert api_key not in str(ticket)
            assert ticket["upload_url"].startswith(f"{BASE}/api/uploads/upl_")

            # 2. Upload the file once, with no credentials, like `curl -T`.
            sent = await shell.put(ticket["upload_url"], content=text_pdf_bytes)
            assert sent.status_code == 200, sent.text
            stored = sent.json()
            assert (stored["image_id"], stored["kind"], stored["pages"]) == (
                ticket["image_id"],
                "pdf",
                3,
            )
            again = await shell.put(ticket["upload_url"], content=text_pdf_bytes)
            assert again.status_code == 404  # the link works once
            image_id = ticket["image_id"]
            assert used() == 0  # nothing so far is metered

            # 3. Choose a page from the listing, for free.
            listing = text_of(await client.call_tool("pdf_pages", {"image_id": image_id}))
            assert "3 page(s)" in listing
            assert "Page 2 (8.5 x 11.0 in): Sheet 2 of 3 Single line diagram" in listing
            previews = await client.call_tool("pdf_pages", {"image_id": image_id, "previews": True})
            assert image_of(previews).size[0] > 0
            assert used() == 0

            # 4. Open only that page.
            opened = await client.call_tool("open_image", {"image_id": image_id, "page": 2})
            assert not opened.is_error
            assert "PDF page 2 of 3" in text_of(opened)
            session_id = session_id_of(opened)
            overview = image_of(opened).size
            assert used() == 1

            # 5. Zoom, zoom deeper, then step back.
            first = await client.call_tool("zoom", {"session_id": session_id, "select": "1-2-A-B"})
            assert not first.is_error, text_of(first)
            assert image_of(first).size[0] > 0
            deeper = await client.call_tool(
                "zoom", {"session_id": session_id, "select": "A1", "zoom": 4}
            )
            assert not deeper.is_error
            assert store.get(E2E_USER, session_id).state.depth == 2

            undone = await client.call_tool("undo", {"session_id": session_id})
            assert "Popped" in text_of(undone)
            assert store.get(E2E_USER, session_id).state.depth == 1
            redone = await client.call_tool("redo", {"session_id": session_id})
            assert store.get(E2E_USER, session_id).state.depth == 2 and not redone.is_error
            shown = await client.call_tool("view", {"session_id": session_id})
            assert "depth 2" in text_of(shown)
            restored = await client.call_tool("restore", {"session_id": session_id})
            assert image_of(restored).size == overview
            assert store.get(E2E_USER, session_id).state.depth == 0

            # 6. Another page of the same upload: no new upload, a new session.
            other = await client.call_tool("open_image", {"image_id": image_id, "page": 3})
            assert "PDF page 3 of 3" in text_of(other)
            assert session_id_of(other) != session_id

            # 7. Errors come back as tool errors and are not charged.
            before = used()
            bad_page = await client.call_tool("open_image", {"image_id": image_id, "page": 9})
            assert bad_page.is_error and "out of range" in text_of(bad_page)
            bad_cell = await client.call_tool("zoom", {"session_id": session_id, "select": "ZZ99"})
            assert bad_cell.is_error
            assert used() == before

            # 8. The usage tool agrees with what was metered.
            usage = (await client.call_tool("usage", {})).structured_content
            assert usage["monthly_used"] == before
            assert usage["open_images"] == 2

    asyncio.run(scenario())


def test_image_from_url_roundtrip(api_key, small_png_bytes, monkeypatch):
    from zoomify import mcp_server

    monkeypatch.setattr(mcp_server, "fetch_url", lambda url, max_bytes: small_png_bytes)

    async def scenario():
        async with connect(api_key) as (client, _):
            opened = await client.call_tool(
                "open_image", {"image_url": "https://example.com/plan.png"}
            )
            assert "Opened 'plan.png' (400x300 px)" in text_of(opened)
            zoomed = await client.call_tool(
                "zoom", {"session_id": session_id_of(opened), "select": "B2"}
            )
            assert "Zoomed selection 'B2'" in text_of(zoomed)
            assert used() == 2

    asyncio.run(scenario())


def _leaf_errors(exc: BaseException) -> list[BaseException]:
    inner = getattr(exc, "exceptions", None)  # an exception group, on any Python version
    if inner:
        return [leaf for each in inner for leaf in _leaf_errors(each)]
    return [exc]


@pytest.mark.parametrize("key", [None, "zfy_live_" + "0" * 24])
def test_client_without_a_valid_key_cannot_connect(api_key, key):
    async def scenario():
        async with connect(key) as (client, _):
            await client.list_tools()

    with pytest.raises(BaseException) as caught:  # noqa: PT011 - the SDK raises a group
        asyncio.run(scenario())
    assert any(isinstance(leaf, MCPError) for leaf in _leaf_errors(caught.value))
    assert used() == 0
