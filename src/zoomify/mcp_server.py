"""Zoomify remote MCP server — zoom tools, skills, and metering for any agent.

Built on the official MCP Python SDK and served over Streamable HTTP at
``/mcp`` by ``zoomify.api.app``. Clients authenticate with a Zoomify platform API key
(``Authorization: Bearer zfy_live_…``).

Tools
-----
Metered (one *request* each): ``open_image``, ``zoom``
Free: ``request_upload``, ``pdf_pages``, ``undo``, ``redo``, ``restore``,
``view``, ``usage``, ``read_skill``

Extending
---------
- New tool: add a function inside :func:`build_mcp` with ``@server.tool``. Call
  :func:`_meter` first if it should count against the plan allowance.
- New skill: drop a Markdown file into ``src/zoomify/skills/`` (see
  :mod:`zoomify.skills`). It is exposed as a resource, a prompt, and through
  ``read_skill`` with no code change.
"""

from __future__ import annotations

import base64
import binascii
import os
import shlex
from typing import Annotated, Any

import anyio
from mcp.server.mcpserver import Context, Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .account.billing import QuotaExceeded, enforce_quota, record_usage
from .account.db import user_billing_status
from .core.images import (
    UPLOAD_TICKET_TTL_SECONDS,
    ImageError,
    Upload,
    describe_upload,
    fetch_url,
    is_pdf,
    load_image,
    pdf_outline,
    uploads,
)
from .account.plans import plan_for_id
from .account.platform_keys import is_platform_key, lookup_clerk_user_by_platform_key
from .core.session import ZoomSession, store
from .skills import CORE_SKILL, get_skill, load_skills, skills_index
from .core.tools import ImageState, encode_view, run_tool

SERVER_NAME = "zoomify"
SERVER_VERSION = "1.0.0"
DEV_USER_ID = "dev-local"
USER_STATE_KEY = "zoomify_user"
BASE_URL_STATE_KEY = "zoomify_base_url"
UPLOAD_PATH = "/api/uploads"

INSTRUCTIONS = """\
Zoomify lets you read images that are too large, dense, or fine-printed to read \
in one look: engineering drawings, single-line diagrams, site plans, maps, \
scans, long screenshots, and PDF pages.

Workflow:
1. open_image(image_url=… or image_id=…) → session_id + the full image with a \
labeled grid (columns A, B, …; rows 1, 2, …).
   The server cannot read files on the user's machine. For a local file, call \
request_upload first: it returns a one-time upload_url and the exact curl \
command to run in your shell, plus the image_id to pass to open_image. The \
upload_url needs no API key, so never look for, read, or ask for the user's key.
2. zoom(session_id, select) on the cells that hold what you need, e.g. "C2" \
(one cell) or "1-3-B-E" (rows 1-3, columns B-E). The crop is upscaled and \
re-gridded so you can zoom again.
3. undo steps back one level, restore returns to the full image, view re-shows \
the current view.

PDFs are sent once and then addressed by page number. A PDF always has an \
image_id (from request_upload, or reported by open_image / pdf_pages when it \
came from a URL): keep it and never upload or download the file again. \
pdf_pages(image_id) is free and gives the page count, each page's text and, \
with previews=true, thumbnails, so you can pick the right page. Then \
open_image(image_id=…, page=N) renders only that page, and you zoom as usual. \
Each page is its own session; say which page every value came from.

Never report a value read from the overview; zoom until the text is sharp, and \
say so if it stays illegible. Grid labels always refer to the current view.

Only open_image and zoom count against the monthly request allowance; \
everything else is free. Call usage to see what is left.

Call read_skill("zoom-basics") before your first extraction, and the skill that \
matches the document type for anything specialised.
"""


class AuthError(Exception):
    """Missing or invalid credentials for the MCP endpoint."""


# --------------------------------------------------------------- auth


def quotas_disabled() -> bool:
    """Self-hosters can switch metering off with ``ZOOMIFY_DISABLE_QUOTAS=true``."""
    return os.environ.get("ZOOMIFY_DISABLE_QUOTAS", "").strip().lower() in ("1", "true", "yes")


def extract_api_key(headers: Any, query: Any = None) -> str | None:
    """Pull a platform key from ``Authorization`` / ``X-API-Key`` / ``?api_key=``."""
    auth = (headers.get("authorization") or "").strip() if headers else ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    alt = (headers.get("x-api-key") or "").strip() if headers else ""
    if alt:
        return alt
    if query is not None:
        value = (query.get("api_key") or "").strip()
        if value:
            return value
    return None


def authenticate(headers: Any, query: Any = None) -> dict[str, Any]:
    """Resolve the calling account. Raises :class:`AuthError` when not allowed.

    With Clerk configured (hosted deployment) a valid platform key is required.
    Without it (local dev / self-hosting) requests fall back to a ``dev-local``
    account so the server works out of the box.
    """
    from .account.clerk_auth import is_clerk_enabled

    key = extract_api_key(headers, query)
    if key:
        if not is_platform_key(key):
            raise AuthError("Invalid API key — expected a Zoomify key starting with zfy_live_.")
        user_id = lookup_clerk_user_by_platform_key(key)
        if not user_id:
            raise AuthError("Invalid or revoked API key.")
        return {"sub": user_id, "auth": "platform_key"}
    if not is_clerk_enabled():
        return {"sub": DEV_USER_ID, "bypass": True}
    raise AuthError(
        "API key required. Create one on the Zoomify connect page and send it as "
        "'Authorization: Bearer zfy_live_…'."
    )


def _user_id(ctx: Context) -> str:
    request = None
    try:
        request = ctx.request_context.request
    except Exception:
        request = None
    if request is not None:
        state = getattr(request, "scope", {}).get("state") or {}
        user = state.get(USER_STATE_KEY)
        if user:
            return str(user["sub"])
        try:
            return str(authenticate(request.headers, request.query_params)["sub"])
        except AuthError as exc:
            raise ToolError(str(exc)) from exc
    try:
        return str(authenticate({})["sub"])
    except AuthError as exc:
        raise ToolError(str(exc)) from exc


# --------------------------------------------------------------- helpers


def public_base_url(request: Any = None) -> str:
    """Origin clients should use to reach this server (no trailing slash)."""
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        state = getattr(request, "scope", {}).get("state") or {}
        if state.get(BASE_URL_STATE_KEY):
            return str(state[BASE_URL_STATE_KEY]).rstrip("/")
        base = getattr(request, "base_url", None)
        if base:
            return str(base).rstrip("/")
    return "http://127.0.0.1:8000"


def _base_url(ctx: Context) -> str:
    try:
        request = ctx.request_context.request
    except Exception:
        request = None
    return public_base_url(request)


def _decode_inline(value: str, max_bytes: int) -> bytes:
    """Decode ``image_base64`` (raw base64 or a ``data:`` URL)."""
    text = value.strip()
    if text.startswith("data:"):
        head, sep, text = text.partition(",")
        if not sep or ";base64" not in head:
            raise ImageError("image_base64 data URLs must be base64-encoded.")
    text = "".join(text.split())
    if len(text) * 3 // 4 > max_bytes + 3:
        raise ImageError(
            f"The inline image is larger than this plan's {max_bytes // (1024 * 1024)} MB "
            "limit. Use request_upload instead."
        )
    try:
        data = base64.b64decode(text + "=" * (-len(text) % 4), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageError(
            "image_base64 is not valid base64. For a file on disk, call request_upload "
            "and upload it with the curl command it returns."
        ) from exc
    if not data:
        raise ImageError("image_base64 is empty.")
    return data


def _resolve_source(
    user_id: str, url: str, upload_id: str, inline: str, max_bytes: int
) -> tuple[bytes, str, Upload | None]:
    """Fetch the bytes behind one of the three sources: ``(data, label, upload)``.

    PDFs that arrive by URL or inline are kept as an upload so every later page
    is served from the stored copy instead of a new download. A URL that was
    already stored is not downloaded again.
    """
    if upload_id:
        upload = uploads.get(user_id, upload_id)
        if upload is None:
            raise ImageError(
                f"Unknown or expired image_id {upload_id!r}. Nothing has been uploaded "
                "under that id, or it is more than an hour old. Call request_upload "
                "and run the curl command it returns, then try again."
            )
        return upload.data, upload.filename or upload_id, upload
    if inline:
        data, label, source = _decode_inline(inline, max_bytes), "inline image", ""
    else:
        cached = uploads.find_by_source(user_id, url)
        if cached is not None:
            return cached.data, cached.filename or cached.id, cached
        data, source = fetch_url(url, max_bytes), url
        label = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1][:80] or url[:80]
    if not is_pdf(data):
        return data, label, None
    if not source:
        label = "inline PDF"
    pages = describe_upload(data)["pages"]
    upload = uploads.put(user_id, data, label, "pdf", pages, source=source)
    return data, label, upload


def _meter(user_id: str) -> dict | None:
    """Check plan limits before a metered tool runs (raises ``ToolError`` if blocked)."""
    if quotas_disabled():
        return None
    try:
        return enforce_quota(user_id)
    except QuotaExceeded as exc:
        raise ToolError(str(exc)) from exc


def _charge(user_id: str, status: dict | None) -> str:
    """Count one request after a metered tool succeeded; returns a short footer."""
    if status is None:
        return ""
    after = record_usage(user_id, status)
    return f" Requests left this month: {after['monthly_remaining']:,}."


def _session(user_id: str, session_id: str) -> ZoomSession:
    session = store.get(user_id, (session_id or "").strip())
    if session is None:
        raise ToolError(
            f"Unknown or expired session {session_id!r}. Sessions close after 30 minutes "
            "without use — call open_image again."
        )
    return session


def _grid_summary(state: ImageState) -> str:
    from .core.gridder import col_label

    meta = state.meta
    return f"Grid: columns A–{col_label(meta.ncols - 1)}, rows 1–{meta.nrows}."


def _view(state: ImageState) -> Image:
    data, fmt = encode_view(state.current)
    return Image(data=data, format=fmt)


def _navigate(user_id: str, session_id: str, tool: str, args: dict) -> tuple[str, Image]:
    session = _session(user_id, session_id)
    with session.lock:
        result = run_tool(tool, args, session.state)
        if result.image is None:
            raise ToolError(result.text)
        text = result.text.replace(" Image shown next.", "")
        return f"{text} {_grid_summary(session.state)}", _view(session.state)


_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
SessionId = Annotated[str, Field(description="The session_id returned by open_image.")]


# --------------------------------------------------------------- server


def build_mcp() -> MCPServer:
    """Create a fully configured Zoomify MCP server instance."""
    skills = load_skills()
    server = MCPServer(
        name=SERVER_NAME,
        title="Zoomify",
        version=SERVER_VERSION,
        instructions=INSTRUCTIONS + "\nSkills:\n" + skills_index(),
        website_url="https://github.com/Zynclo-Softwares/Zoomify",
    )

    # ---- metered tools ------------------------------------------------

    @server.tool(
        title="Open image",
        structured_output=False,
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
    )
    async def open_image(
        ctx: Context,
        image_url: Annotated[
            str | None,
            Field(description="Public http(s) URL of an image or PDF for the server to download."),
        ] = None,
        image_id: Annotated[
            str | None,
            Field(
                description=(
                    "Id of an uploaded file, e.g. 'img_…'. For a local or private file, "
                    "call request_upload, run the curl command it returns, then pass the "
                    "image_id here."
                )
            ),
        ] = None,
        image_base64: Annotated[
            str | None,
            Field(
                description=(
                    "The image or PDF itself as base64 (or a data: URL). Only for small "
                    "files you already hold in memory, such as a screenshot; for files on "
                    "disk use request_upload, which costs no tokens."
                )
            ),
        ] = None,
        page: Annotated[
            int,
            Field(
                ge=1,
                description=(
                    "For PDFs: 1-based page number to render (default 1). Only this page "
                    "is rendered. Use pdf_pages to find the right page first."
                ),
            ),
        ] = 1,
        grid_cols: Annotated[
            int | None,
            Field(
                ge=3,
                le=24,
                description="Columns in the root grid. Omit to auto-pick from the image size.",
            ),
        ] = None,
    ) -> list[Any]:
        """Open an image or PDF page and start a zoom session.

        Returns a `session_id` and the full image with a labeled grid overlaid
        (columns A, B, …; rows 1, 2, …). Pass exactly one of `image_url`,
        `image_id`, or `image_base64`. For a file on the user's machine, call
        `request_upload` first. Supports PNG, JPEG, WebP, TIFF, GIF, BMP, and
        PDF. Then call `zoom` with cells from the grid to read detail.

        A PDF is stored once and opened one page per session: the result names
        its `image_id`, so open any other page with
        `open_image(image_id=…, page=N)` without sending the file again. Call
        `pdf_pages` (free) to see the page count and choose a page. Counts as
        one request.
        """
        user_id = _user_id(ctx)
        url = (image_url or "").strip()
        upload_id = (image_id or "").strip()
        inline = (image_base64 or "").strip()
        if sum(map(bool, (url, upload_id, inline))) != 1:
            raise ToolError(
                "Pass exactly one of image_url, image_id, or image_base64. For a local "
                "file, call request_upload first."
            )

        status = _meter(user_id)
        plan = plan_for_id(status["plan"] if status else "pro")
        max_bytes = plan.max_image_mb * 1024 * 1024

        def work() -> tuple[ZoomSession, list[str], Upload | None]:
            data, label, upload = _resolve_source(user_id, url, upload_id, inline, max_bytes)
            loaded = load_image(data, page=page)
            state = ImageState.from_image(loaded.image, cols=grid_cols)
            session, evicted = store.create(
                user_id,
                state,
                label=label,
                max_open=plan.max_open_images,
                source_kind=loaded.source_kind,
                page=loaded.page,
                page_count=loaded.page_count,
            )
            return session, evicted, upload

        try:
            session, evicted, upload = await anyio.to_thread.run_sync(work)
        except ImageError as exc:
            raise ToolError(str(exc)) from exc

        w, h = session.state.original.size
        parts = [
            f"Opened {session.label!r} ({w}x{h} px) as session_id {session.id}.",
            _grid_summary(session.state),
        ]
        if session.source_kind == "pdf":
            parts.append(f"PDF page {session.page} of {session.page_count}.")
            if session.page_count > 1 and upload is not None:
                parts.append(
                    f"The PDF is stored as image_id {upload.id}: open another page with "
                    f"open_image(image_id='{upload.id}', page=N), or call pdf_pages to "
                    "pick one. Do not send the file again."
                )
        parts.append(
            "This overview is only for locating things: call zoom with cells such as "
            "'C2' or '1-3-B-E' before reading any values."
        )
        if evicted:
            parts.append(
                f"Closed {len(evicted)} older session(s) to stay within this plan's "
                f"{plan.max_open_images} open images."
            )
        text = " ".join(parts) + _charge(user_id, status)
        return [text, _view(session.state)]

    @server.tool(title="Zoom", structured_output=False, annotations=_READ_ONLY)
    async def zoom(
        ctx: Context,
        session_id: SessionId,
        select: Annotated[
            str,
            Field(
                description=(
                    "Cells/regions of the CURRENT view to zoom into. '2C' or 'C2' (one cell), "
                    "'1C,3B,4C' (several cells), '1-3-B-E' (rows 1-3 x columns B-E), "
                    "'1-2-A-F, 3-5-G-J' (several regions). The crop is their bounding box."
                )
            ),
        ],
        zoom: Annotated[
            float,
            Field(ge=1, le=8, description="Upscale factor (default 3). Use 4-6 for tiny fonts."),
        ] = 3,
        regrid_cols: Annotated[
            int | None,
            Field(
                ge=2,
                le=30,
                description="Columns for the fresh grid on the zoomed crop. Omit to auto-pick.",
            ),
        ] = None,
    ) -> list[Any]:
        """Crop the selected cells from the current view, upscale, and re-grid.

        Use this to read small text and drill deeper: the result carries a new
        labeled grid, so you can zoom again. Pushes a step onto the session's
        zoom stack — `undo` steps back if you picked the wrong region. Counts
        as one request (failed selections are not counted).
        """
        user_id = _user_id(ctx)
        session = _session(user_id, session_id)
        status = _meter(user_id)

        def work() -> tuple[str, Image]:
            with session.lock:
                args: dict[str, Any] = {"select": select, "zoom": zoom}
                if regrid_cols is not None:
                    args["regrid_cols"] = regrid_cols
                result = run_tool("zoom", args, session.state)
                if result.image is None:
                    raise ImageError(result.text)
                text = result.text.replace(" Image shown next.", "")
                return f"{text} {_grid_summary(session.state)}", _view(session.state)

        try:
            text, image = await anyio.to_thread.run_sync(work)
        except (ImageError, ValueError) as exc:
            raise ToolError(str(exc)) from exc
        return [text + _charge(user_id, status), image]

    # ---- free navigation ----------------------------------------------

    @server.tool(title="Undo zoom", structured_output=False, annotations=_READ_ONLY)
    async def undo(ctx: Context, session_id: SessionId) -> list[Any]:
        """Step back one zoom level and show that view again.

        Use when the last zoom targeted the wrong cells — you land on the parent
        view and can zoom somewhere else. Free (not counted as a request).
        """
        user_id = _user_id(ctx)
        text, image = await anyio.to_thread.run_sync(_navigate, user_id, session_id, "undo", {})
        return [text, image]

    @server.tool(title="Redo zoom", structured_output=False, annotations=_READ_ONLY)
    async def redo(ctx: Context, session_id: SessionId) -> list[Any]:
        """Re-apply the zoom step most recently removed by `undo`.

        Only the latest undo can be redone, and a new `zoom` clears it. Free.
        """
        user_id = _user_id(ctx)
        text, image = await anyio.to_thread.run_sync(_navigate, user_id, session_id, "redo", {})
        return [text, image]

    @server.tool(title="Restore full image", structured_output=False, annotations=_READ_ONLY)
    async def restore(ctx: Context, session_id: SessionId) -> list[Any]:
        """Clear the zoom stack and return to the full gridded image. Free."""
        user_id = _user_id(ctx)
        text, image = await anyio.to_thread.run_sync(_navigate, user_id, session_id, "restore", {})
        return [text, image]

    @server.tool(title="Show current view", structured_output=False, annotations=_READ_ONLY)
    async def view(ctx: Context, session_id: SessionId) -> list[Any]:
        """Show the current view again without changing the zoom stack.

        Use when the image has dropped out of your context or you need to
        re-check the grid labels before the next zoom. Free.
        """
        user_id = _user_id(ctx)

        def work() -> tuple[str, Image]:
            session = _session(user_id, session_id)
            with session.lock:
                trail = " → ".join(session.state.checkpoint_labels())
                text = (
                    f"Current view of {session.label!r} at depth {session.state.depth} "
                    f"({trail}). {_grid_summary(session.state)}"
                )
                return text, _view(session.state)

        text, image = await anyio.to_thread.run_sync(work)
        return [text, image]

    # ---- uploads --------------------------------------------------------

    @server.tool(
        title="Request an upload link",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def request_upload(
        ctx: Context,
        file_path: Annotated[
            str | None,
            Field(
                description=(
                    "Path of the local file you intend to upload. Optional; it is only "
                    "used to fill in the returned curl command."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Get a one-time link for uploading a local image or PDF, with no API key.

        Use this whenever the image is a file on the user's machine. Run the
        returned `curl` command in your shell (it sends the file straight from
        disk, so the file never passes through your context), then call
        `open_image(image_id=…)` with the returned `image_id`. A multi-page PDF
        is uploaded once: the same `image_id` serves every page through
        `pdf_pages` and `open_image(page=N)`. The link works once, for one
        file, and expires in 15 minutes. Do not read or ask for
        the user's API key. Free.
        """
        user_id = _user_id(ctx)
        status = await anyio.to_thread.run_sync(user_billing_status, user_id)
        plan = plan_for_id(status["plan"])
        path = (file_path or "").strip()
        name = path.replace("\\", "/").rsplit("/", 1)[-1][:200]
        ticket = uploads.issue_ticket(user_id, plan.max_image_mb * 1024 * 1024, filename=name)
        upload_url = f"{_base_url(ctx)}{UPLOAD_PATH}/{ticket.token}"
        path = path or "/path/to/file"
        return {
            "image_id": ticket.image_id,
            "upload_url": upload_url,
            "curl": f"curl -sS -T {shlex.quote(path)} {shlex.quote(upload_url)}",
            "method": "PUT (raw file body) or POST (multipart field 'file')",
            "max_mb": plan.max_image_mb,
            "expires_in_seconds": UPLOAD_TICKET_TTL_SECONDS,
            "next": (
                f"After the upload succeeds, call open_image(image_id='{ticket.image_id}'). "
                f"For a multi-page PDF, call pdf_pages(image_id='{ticket.image_id}') to pick "
                "a page, then open_image with that page number. Upload once only."
            ),
        }

    @server.tool(
        title="List PDF pages",
        structured_output=False,
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
    )
    async def pdf_pages(
        ctx: Context,
        image_id: Annotated[
            str | None,
            Field(
                description="Id of a stored PDF, e.g. 'img_…' (from request_upload or open_image)."
            ),
        ] = None,
        image_url: Annotated[
            str | None,
            Field(
                description=(
                    "Public http(s) URL of a PDF. The server downloads it once, stores it, "
                    "and returns an image_id to use from then on."
                )
            ),
        ] = None,
        pages: Annotated[
            str | None,
            Field(
                description=(
                    "Pages to describe: '3', '2-6', or '1,4,9-12'. Omit to list from page 1. "
                    "A single page returns its full text instead of a snippet."
                )
            ),
        ] = None,
        previews: Annotated[
            bool,
            Field(
                description=(
                    "Also return one contact sheet of small page thumbnails (up to 12 pages "
                    "per call). Use it for scans and drawings whose pages have no text."
                )
            ),
        ] = False,
    ) -> list[Any]:
        """Look inside a multi-page PDF to choose which page to open.

        Returns the PDF's `image_id`, its page count, and for each listed page
        its size and the start of its text. Ask for one page to get its text in
        full, or set `previews` for thumbnails when pages are scans or drawings
        without text. Then call `open_image(image_id=…, page=N)` on the page you
        need; only that page is rendered. The PDF is stored once, so nothing is
        uploaded or downloaded again. The text and thumbnails are for choosing a
        page: read values with `open_image` and `zoom`. Free.
        """
        user_id = _user_id(ctx)
        url = (image_url or "").strip()
        upload_id = (image_id or "").strip()
        if bool(url) == bool(upload_id):
            raise ToolError(
                "Pass exactly one of image_id or image_url. For a local file, call "
                "request_upload first."
            )
        status = await anyio.to_thread.run_sync(user_billing_status, user_id)
        max_bytes = plan_for_id(status["plan"]).max_image_mb * 1024 * 1024

        def work() -> tuple[str, Any, Upload | None]:
            data, label, upload = _resolve_source(user_id, url, upload_id, "", max_bytes)
            return label, pdf_outline(data, pages=pages, previews=previews), upload

        try:
            label, outline, upload = await anyio.to_thread.run_sync(work)
        except ImageError as exc:
            raise ToolError(str(exc)) from exc

        ref = upload.id if upload is not None else upload_id
        lines = [
            f"{label!r} is a PDF with {outline.page_count} page(s), stored as image_id {ref}. "
            f"Open a page with open_image(image_id='{ref}', page=N)."
        ]
        for info in outline.pages:
            head = f"Page {info.page} ({info.width_in} x {info.height_in} in)"
            if not info.text_chars:
                lines.append(f"{head}: no text layer (scan or drawing).")
            elif len(outline.pages) == 1:
                cut = " (cut)" if info.text_chars > len(info.text) else ""
                lines.append(f"{head}, text{cut}:\n{info.text}")
            else:
                more = "…" if info.text_chars > len(info.text) else ""
                lines.append(f"{head}: {' '.join(info.text.split())}{more}")
        if outline.truncated:
            last = outline.pages[-1].page
            lines.append(
                f"Listed through page {last}. Call pdf_pages again with pages="
                f"'{last + 1}-{outline.page_count}' for the rest."
            )
        if any(not info.text_chars for info in outline.pages) and not previews:
            lines.append("Pages without text can be told apart with previews=true.")
        lines.append(
            "Page text and thumbnails are for choosing a page; zoom before reporting values."
        )
        result: list[Any] = ["\n".join(lines)]
        if outline.preview is not None:
            data, fmt = encode_view(outline.preview)
            result.append(Image(data=data, format=fmt))
        return result

    # ---- account & guidance -------------------------------------------

    @server.tool(title="Plan & usage", annotations=_READ_ONLY)
    async def usage(ctx: Context) -> dict[str, Any]:
        """Report the account's plan, requests used and left this month, and limits.

        Free. Only `open_image` and `zoom` count as requests.
        """
        user_id = _user_id(ctx)
        status = await anyio.to_thread.run_sync(user_billing_status, user_id)
        status = {k: v for k, v in status.items() if k != "current_period_end"}
        status["open_images"] = store.count(user_id)
        status["metering"] = "disabled" if quotas_disabled() else "enabled"
        return status

    @server.tool(
        title="Read a skill",
        structured_output=False,
        annotations=_READ_ONLY,
        description=(
            "Return a Zoomify skill — a short playbook on using these tools well for a "
            "kind of document. Read 'zoom-basics' before your first extraction. Free.\n\n"
            "Available skills:\n" + skills_index()
        ),
    )
    async def read_skill(
        name: Annotated[str, Field(description="Skill name, e.g. 'zoom-basics'.")] = CORE_SKILL,
    ) -> str:
        skill = get_skill(name)
        if skill is None:
            raise ToolError(f"Unknown skill {name!r}. Available: {', '.join(load_skills())}.")
        return skill.body

    # ---- skills as resources and prompts ------------------------------

    def _register_skill(skill) -> None:
        def resource_fn() -> str:
            return skill.body

        resource_fn.__name__ = "skill_" + skill.name.replace("-", "_")
        server.resource(
            skill.uri,
            name=skill.name,
            title=skill.title,
            description=skill.description,
            mime_type="text/markdown",
        )(resource_fn)

        def prompt_fn() -> str:
            return skill.body

        prompt_fn.__name__ = resource_fn.__name__
        server.prompt(name=skill.name, title=skill.title, description=skill.description)(prompt_fn)

    for skill in skills.values():
        _register_skill(skill)

    @server.prompt(
        name="inspect-image",
        title="Inspect an image with Zoomify",
        description="Start a careful, zoom-first extraction from an image or PDF.",
    )
    def inspect_image(image: str, task: str = "Extract the key information.") -> str:
        """`image` is a URL, an image_id, or a local file path; `task` is what to find."""
        core = get_skill(CORE_SKILL)
        guide = core.body if core else ""
        ref = image.strip()
        if ref.startswith("img_"):
            how = f"Image (image_id): {ref}"
        elif ref.lower().startswith(("http://", "https://")):
            how = f"Image (image_url): {ref}"
        else:
            how = (
                f"Image (local file): {ref}\nCall request_upload with that path, run the "
                "curl command it returns, then open the returned image_id."
            )
        return (
            f"{guide}\n\n---\n\nUse the Zoomify tools to complete this task.\n\n"
            f"{how}\nTask: {task.strip()}\n\n"
            "Open the image, zoom until every value you report is sharp, and cite the "
            "region each value came from."
        )

    return server


def tools_catalog() -> list[dict[str, Any]]:
    """Static summary of the tools for the web setup page."""
    return [
        {
            "name": "open_image",
            "metered": True,
            "summary": "Open an image or PDF page; returns a session and the gridded overview.",
        },
        {
            "name": "zoom",
            "metered": True,
            "summary": "Crop the selected grid cells, upscale, and re-grid to read small detail.",
        },
        {"name": "undo", "metered": False, "summary": "Step back one zoom level."},
        {"name": "redo", "metered": False, "summary": "Re-apply the zoom step you just undid."},
        {"name": "restore", "metered": False, "summary": "Return to the full gridded image."},
        {"name": "view", "metered": False, "summary": "Show the current view again."},
        {
            "name": "request_upload",
            "metered": False,
            "summary": "One-time upload link so an agent can send a local file without the key.",
        },
        {
            "name": "pdf_pages",
            "metered": False,
            "summary": "Page count, page text, and thumbnails of a stored PDF, to pick a page.",
        },
        {
            "name": "usage",
            "metered": False,
            "summary": "Plan, requests left this month, and limits.",
        },
        {
            "name": "read_skill",
            "metered": False,
            "summary": "Load a playbook for a kind of document.",
        },
    ]
