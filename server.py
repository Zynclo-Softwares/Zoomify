"""Zoomify server — remote MCP endpoint (`/mcp`) plus the account API and web UI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from zoomify.billing import billing_plans_payload
from zoomify.clerk_auth import is_clerk_enabled, require_clerk_user, require_user
from zoomify.db import ensure_indexes, mongodb_database_name, mongodb_enabled, user_billing_status
from zoomify.github_issues import create_schema_inquiry_issue, github_issues_configured
from zoomify.images import UPLOAD_TTL_SECONDS, ImageError, describe_upload, uploads
from zoomify.mcp_server import (
    SERVER_VERSION,
    USER_STATE_KEY,
    AuthError,
    authenticate,
    build_mcp,
    quotas_disabled,
    tools_catalog,
)
from zoomify.openapi import OPENAPI_TAGS, customize_openapi
from zoomify.plans import plan_for_id
from zoomify.platform_keys import (
    create_platform_key,
    platform_key_status,
    rotate_platform_key,
)
from zoomify.skills import get_skill, load_skills
from zoomify.stripe_webhook import handle_event, stripe_configured, verify_and_parse

load_dotenv()

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
MCP_PATH = "/mcp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("AUTO_CREATE_INDEXES_ON_BOOT", "true").lower() in ("1", "true", "yes"):
        try:
            ensure_indexes()
        except Exception:
            pass

    # A session manager can only run once, so build a fresh MCP server per app
    # lifespan. Stateless + JSON responses: every request is self-contained
    # (zoom state lives in Zoomify sessions, not in the MCP transport), which
    # keeps the endpoint friendly to proxies and restarts.
    mcp = build_mcp()
    mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # Auth is a bearer key, not ambient browser credentials, so Host/Origin
        # pinning (meant for localhost servers) does not apply to this deployment.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    async with mcp.session_manager.run():
        app.state.mcp_manager = mcp.session_manager
        try:
            yield
        finally:
            app.state.mcp_manager = None


app = FastAPI(
    title="Zoomify API",
    version=SERVER_VERSION,
    description="Account, billing, and upload API for the Zoomify MCP server.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)


def _openapi():
    return customize_openapi(app)


app.openapi = _openapi  # type: ignore[method-assign]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)


def _user_id(user: dict) -> str:
    return str(user.get("sub") or "dev-local")


# --------------------------------------------------------------- MCP endpoint


async def mcp_endpoint(scope: Scope, receive: Receive, send: Send) -> None:
    """Authenticate with a platform key, then hand the request to the MCP transport."""
    request = Request(scope, receive)
    try:
        user = await run_in_threadpool(authenticate, request.headers, request.query_params)
    except AuthError as exc:
        response = JSONResponse(
            {"error": "unauthorized", "message": str(exc)},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="zoomify"'},
        )
        await response(scope, receive, send)
        return

    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is None:
        response = JSONResponse(
            {"error": "unavailable", "message": "MCP server is starting."}, status_code=503
        )
        await response(scope, receive, send)
        return

    scope.setdefault("state", {})[USER_STATE_KEY] = user
    await manager.handle_request(scope, receive, send)


class _MCPApp:
    """Class wrapper so Starlette treats the endpoint as a raw ASGI app (all methods)."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await mcp_endpoint(scope, receive, send)


app.router.routes.append(Route(MCP_PATH, endpoint=_MCPApp()))
app.router.routes.append(Route(MCP_PATH + "/", endpoint=_MCPApp()))


# --------------------------------------------------------------- system


@app.get("/api/health", tags=["system"])
def health():
    """Service status flags (no auth required)."""
    return {
        "ok": True,
        "version": SERVER_VERSION,
        "mcp_path": MCP_PATH,
        "clerk_enabled": is_clerk_enabled(),
        "metering_enabled": not quotas_disabled(),
        "mongodb_enabled": mongodb_enabled(),
        "mongodb_database": mongodb_database_name() if mongodb_enabled() else None,
        "stripe_webhook_configured": stripe_configured(),
        "contact_form_configured": github_issues_configured(),
    }


@app.get("/api/mcp/info", tags=["system"])
def mcp_info(request: Request):
    """Everything a client needs to connect: endpoint URL, auth scheme, tools, skills."""
    base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/") or str(
        request.base_url
    ).rstrip("/")
    return {
        "name": "zoomify",
        "version": SERVER_VERSION,
        "transport": "streamable-http",
        "url": base + MCP_PATH,
        "upload_url": base + "/api/images",
        "auth": {
            "type": "bearer",
            "header": "Authorization",
            "format": "Bearer zfy_live_…",
            "required": is_clerk_enabled(),
        },
        "tools": tools_catalog(),
        "skills": [s.public() for s in load_skills().values()],
    }


# --------------------------------------------------------------- skills


@app.get("/api/skills", tags=["skills"])
def list_skills():
    """Agent skills bundled with the server (also served over MCP)."""
    return {"skills": [s.public(include_body=True) for s in load_skills().values()]}


@app.get("/api/skills/{name}.md", tags=["skills"], response_class=PlainTextResponse)
def skill_markdown(name: str):
    """One skill as a standalone SKILL.md document."""
    skill = get_skill(name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Unknown skill")
    return PlainTextResponse(skill.as_markdown(), media_type="text/markdown; charset=utf-8")


# --------------------------------------------------------------- auth & keys


@app.get("/api/auth/me", tags=["auth"])
def auth_me(user: dict = Depends(require_user)):
    """Who am I? Accepts platform key or Clerk JWT in `Authorization`."""
    return {
        "user_id": user.get("sub"),
        "email": user.get("email") or user.get("primary_email_address"),
        "auth": user.get("auth") or ("bypass" if user.get("bypass") else None),
        "bypass": bool(user.get("bypass")),
    }


@app.get("/api/platform-key", tags=["auth"])
def get_platform_key(user: dict = Depends(require_user)):
    """Whether this account has a platform key (prefix only — never the secret)."""
    return platform_key_status(_user_id(user))


@app.post("/api/platform-key", tags=["auth"])
def post_platform_key(user: dict = Depends(require_clerk_user)):
    """Create the account's single platform API key. Full key returned once (Clerk JWT only)."""
    try:
        return create_platform_key(_user_id(user))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/platform-key/rotate", tags=["auth"])
def rotate_platform_key_route(user: dict = Depends(require_user)):
    """Replace the platform API key. New key returned once; old key stops working immediately."""
    try:
        return rotate_platform_key(_user_id(user))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --------------------------------------------------------------- uploads


@app.post("/api/images", tags=["images"])
async def upload_image(
    file: UploadFile = File(..., description="Image (PNG, JPEG, WebP, TIFF, GIF, BMP) or PDF."),
    user: dict = Depends(require_user),
):
    """Upload a local image or PDF and get an `image_id` for the `open_image` tool.

    Uploads are private to your account, held in memory, and expire after one
    hour. Uploading is free — `open_image` is what counts as a request.

    ```bash
    curl -s -H "Authorization: Bearer $ZOOMIFY_API_KEY" \\
         -F "file=@drawing.pdf" https://<host>/api/images
    ```
    """
    user_id = _user_id(user)
    plan = plan_for_id(user_billing_status(user_id)["plan"])
    max_bytes = plan.max_image_mb * 1024 * 1024

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File is larger than the {plan.name} plan's {plan.max_image_mb} MB limit.",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=422, detail="The file is empty.")

    try:
        info = await run_in_threadpool(describe_upload, data)
    except ImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upload = uploads.put(
        user_id, data, filename=file.filename or "", kind=info["kind"], pages=info["pages"]
    )
    return {
        "image_id": upload.id,
        "filename": upload.filename,
        "kind": upload.kind,
        "pages": upload.pages,
        "bytes": len(data),
        "expires_in_seconds": UPLOAD_TTL_SECONDS,
        "expires_at": datetime.fromtimestamp(upload.expires_at, tz=UTC).isoformat(),
    }


# --------------------------------------------------------------- billing


@app.get("/api/billing/plans", tags=["billing"])
def billing_plans():
    """Public plan catalog and Stripe Payment Link URLs."""
    return billing_plans_payload()


@app.get("/api/billing/status", tags=["billing"])
def billing_status(user: dict = Depends(require_user)):
    """Current plan and this month's request usage (requires Zoomify auth)."""
    return user_billing_status(_user_id(user))


@app.post("/api/billing/webhook", tags=["billing"])
async def billing_webhook(request: Request):
    """Stripe subscription lifecycle webhook."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = verify_and_parse(payload, sig)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return handle_event(event)


# --------------------------------------------------------------- contact


class SchemaInquiryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    message: str = Field(min_length=1, max_length=8000)


@app.post("/api/schema-inquiry", tags=["support"])
def schema_inquiry(body: SchemaInquiryRequest):
    """Create a GitHub issue for a custom skills / enterprise inquiry (public form)."""
    try:
        return create_schema_inquiry_issue(
            name=body.name,
            email=body.email,
            message=body.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# --------------------------------------------------------------- web UI


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (FRONTEND_DIST / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
