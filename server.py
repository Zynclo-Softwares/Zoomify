"""FastAPI backend for Zoomify (React UI + streaming query API)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from zoomify.billing import billing_plans_payload, enforce_query_quota, record_query_usage
from zoomify.byok_crypto import HEADER_NAME, decrypt_api_key, is_byok_ready, public_key_pem
from zoomify.clerk_auth import is_clerk_enabled, require_clerk_user
from zoomify.db import ensure_indexes, mongodb_database_name, mongodb_enabled, user_billing_status
from zoomify.openrouter_models import model_dropdown_update
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
        "Bring your own OpenRouter key via encrypted header. Platform usage is metered on "
        "`POST /api/query`."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

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
    if not is_byok_ready():
        raise HTTPException(status_code=503, detail="BYOK encryption is not configured")
    return {"public_key_pem": public_key_pem()}


def require_openrouter_key(request: Request) -> str:
    encrypted = request.headers.get(HEADER_NAME, "").strip()
    if not encrypted:
        raise HTTPException(status_code=401, detail="Encrypted OpenRouter API key required")
    try:
        return decrypt_api_key(encrypted)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid encrypted API key") from exc


@app.get("/api/auth/me", tags=["auth"])
def auth_me(user: dict = Depends(require_clerk_user)):
    return {
        "user_id": user.get("sub"),
        "email": user.get("email") or user.get("primary_email_address"),
        "bypass": bool(user.get("bypass")),
    }


@app.get("/api/billing/plans", tags=["billing"])
def billing_plans():
    """Public plan catalog, Stripe Payment Link URLs, and premium schema service."""
    return billing_plans_payload()


@app.get("/api/billing/status", tags=["billing"])
def billing_status(user: dict = Depends(require_clerk_user)):
    """Current plan and daily extraction usage for the signed-in user."""
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


@app.get("/api/models", tags=["query"])
def list_models(
    _user: dict = Depends(require_clerk_user),
    api_key: str = Depends(require_openrouter_key),
):
    upd = model_dropdown_update(api_key=api_key)
    return {"choices": upd["choices"], "default": upd["value"]}


@app.post("/api/query", tags=["query"])
async def query(
    query: str = Form(""),
    model: str | None = Form(None),
    schema_param: str | None = Form(None, alias="schema"),
    structured: bool = Form(True),
    session_id: str | None = Form(None),
    image: UploadFile | None = File(None),
    user: dict = Depends(require_clerk_user),
    api_key: str = Depends(require_openrouter_key),
):
    """Stream agent progress as NDJSON (one JSON object per line).

    Accepts exactly one optional image per request. Optional ``schema`` must
    match a registered business schema id. Set ``structured=false`` to force
    free-text even when image metadata tags a schema.

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
def delete_session(session_id: str, _user: dict = Depends(require_clerk_user)):
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
