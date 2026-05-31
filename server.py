"""FastAPI backend for Zoomify (React UI + streaming query API)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from zoomify.billing import billing_plans_payload, enforce_query_quota, record_query_usage
from zoomify.byok_crypto import HEADER_NAME, decrypt_api_key, is_byok_ready, public_key_pem
from zoomify.clerk_auth import is_clerk_enabled, require_clerk_user, require_user
from zoomify.db import ensure_indexes, mongodb_database_name, mongodb_enabled, user_billing_status
from zoomify.openapi import NDJSON_STREAM_RESPONSE, OPENAPI_TAGS, customize_openapi
from zoomify.platform_keys import (
    create_platform_key,
    platform_key_status,
    rotate_platform_key,
)
from zoomify.openrouter_models import check_openrouter_health, model_dropdown_update
from zoomify.query_runner import run_query_stream
from zoomify.session import store
from zoomify.stripe_webhook import handle_event, stripe_configured, verify_and_parse

load_dotenv()

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

app = FastAPI(
    title="Zoomify API",
    version="0.2.0",
    description=(
        "Vision extraction API with smart zoom grid, live trail, and optional structured JSON. "
        "See the description below for authentication (`Authorization` + `X-Encrypted-Api-Key`)."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=OPENAPI_TAGS,
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
)


@app.on_event("startup")
def _startup():
    if os.environ.get("AUTO_CREATE_INDEXES_ON_BOOT", "true").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        ensure_indexes()
    except Exception:
        pass


def _user_id(user: dict) -> str:
    return str(user.get("sub") or "dev-local")


@app.get("/api/health", tags=["system"])
def health():
    """Service status flags (no auth required)."""
    return {
        "ok": True,
        "byok_ready": is_byok_ready(),
        "clerk_enabled": is_clerk_enabled(),
        "mongodb_enabled": mongodb_enabled(),
        "mongodb_database": mongodb_database_name() if mongodb_enabled() else None,
        "stripe_webhook_configured": stripe_configured(),
    }


@app.get("/api/byok/public-key", tags=["byok"])
def byok_public_key():
    """RSA public key PEM for client-side OpenRouter key encryption (no auth required)."""
    if not is_byok_ready():
        raise HTTPException(status_code=503, detail="BYOK encryption is not configured")
    return {"public_key_pem": public_key_pem()}


_encrypted_openrouter_header = APIKeyHeader(
    name=HEADER_NAME,
    scheme_name="EncryptedOpenRouterKey",
    description=(
        "RSA-OAEP (SHA-256) encrypted OpenRouter API key, base64-encoded. "
        "Encrypt your `sk-or-v1-…` key with the PEM from `GET /api/byok/public-key`. "
        "Never send the OpenRouter key in plain text."
    ),
    auto_error=False,
)


def require_openrouter_key(
    encrypted: str | None = Depends(_encrypted_openrouter_header),
) -> str:
    if not encrypted or not encrypted.strip():
        raise HTTPException(status_code=401, detail="Encrypted OpenRouter API key required")
    try:
        return decrypt_api_key(encrypted.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid encrypted API key") from exc


@app.get("/api/openrouter/health", tags=["system"])
def openrouter_health(api_key: str = Depends(require_openrouter_key)):
    """Validate the encrypted OpenRouter key (requires `X-Encrypted-Api-Key` only)."""
    return check_openrouter_health(api_key=api_key)


@app.get("/api/auth/me", tags=["auth"])
def auth_me(user: dict = Depends(require_user)):
    """Who am I? Accepts platform key or Clerk JWT in `Authorization`."""
    return {
        "user_id": user.get("sub"),
        "email": user.get("email") or user.get("primary_email_address"),
        "auth": user.get("auth") or ("bypass" if user.get("bypass") else None),
        "bypass": bool(user.get("bypass")),
    }


@app.get("/api/billing/plans", tags=["billing"])
def billing_plans():
    """Public plan catalog, Stripe Payment Link URLs, and premium schema service."""
    return billing_plans_payload()


@app.get("/api/billing/status", tags=["billing"])
def billing_status(user: dict = Depends(require_user)):
    """Current plan and daily extraction usage (requires Zoomify auth)."""
    return user_billing_status(_user_id(user))


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


@app.get("/api/models", tags=["query"])
def list_models(
    _user: dict = Depends(require_user),
    api_key: str = Depends(require_openrouter_key),
):
    """List vision-capable OpenRouter models (requires Zoomify auth + encrypted OpenRouter key)."""
    upd = model_dropdown_update(api_key=api_key)
    return {"choices": upd["choices"], "default": upd["value"]}


@app.post(
    "/api/query",
    tags=["query"],
    response_class=StreamingResponse,
    responses={
        200: NDJSON_STREAM_RESPONSE,
        401: {"description": "Missing or invalid Zoomify auth and/or encrypted OpenRouter key"},
        429: {"description": "Daily extraction limit reached for your plan"},
    },
)
async def query(
    query: str = Form(
        "",
        description="Natural-language instruction for what to extract from the image.",
        examples=["Read all part numbers and quantities"],
    ),
    model: str | None = Form(
        None,
        description="OpenRouter model id (e.g. from `GET /api/models`).",
        examples=["anthropic/claude-sonnet-4"],
    ),
    schema_param: str | None = Form(
        None,
        alias="schema",
        description="Registered business schema id (optional). Ignored when `structured=false`.",
        examples=["acme-sld-v1"],
    ),
    structured: bool = Form(
        True,
        description="When true, return JSON matching the resolved schema when possible.",
    ),
    session_id: str | None = Form(
        None,
        description="Resume a prior conversation; omit to start a new session.",
    ),
    image: UploadFile | None = File(
        None,
        description="One image to analyze (PNG, JPEG, etc.). Optional for follow-up text turns.",
    ),
    user: dict = Depends(require_user),
    api_key: str = Depends(require_openrouter_key),
):
    """Stream extraction progress as NDJSON (one JSON object per line).

    **Auth:** Authorize **both** `ZoomifyAuth` and `EncryptedOpenRouterKey` in Swagger.

    **Response events:** `session`, `user`, `trail`, `assistant`, `schema`, `error`, `done`.

    Each successful request counts as one extraction against your daily plan limit.
    """
    clerk_id = _user_id(user)
    enforce_query_quota(clerk_id)
    record_query_usage(clerk_id)

    sid, session = store.get(session_id)

    image_bytes: bytes | None = None
    if image is not None and image.filename:
        raw = await image.read()
        if raw:
            image_bytes = raw

    def event_stream():
        yield json.dumps({"type": "session", "session_id": sid}) + "\n"
        for event in run_query_stream(
            session=session,
            query=query,
            image_bytes=image_bytes,
            api_key=api_key,
            model=model,
            schema_param=schema_param,
            structured=structured,
        ):
            if event.get("type") == "error":
                yield json.dumps(event) + "\n"
                return
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.delete("/api/session/{session_id}", tags=["query"])
def delete_session(
    session_id: str,
    _user: dict = Depends(require_user),
):
    """Clear server-side session state for a session id (requires Zoomify auth)."""
    store.delete(session_id)
    return {"ok": True}


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def spa_root():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
