"""FastAPI backend for Zoomify (React UI + streaming query API)."""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from zoomify.config import api_key, has_api_key
from zoomify.openrouter_models import model_dropdown_update
from zoomify.query_runner import run_query_stream
from zoomify.session import store

load_dotenv()

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

app = FastAPI(title="Zoomify API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "has_api_key": has_api_key()}


@app.get("/api/models")
def list_models():
    upd = model_dropdown_update(api_key=api_key())
    return {"choices": upd["choices"], "default": upd["value"]}


@app.post("/api/query")
async def query(
    query: str = Form(""),
    model: str | None = Form(None),
    schema: str | None = Form(None),
    structured: bool = Form(True),
    session_id: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    """Stream agent progress as NDJSON (one JSON object per line).

    Accepts exactly one optional image per request. Optional ``schema`` must
    match a registered business schema id. Set ``structured=false`` to force
    free-text even when image metadata tags a schema.
    """
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
            model=model,
            schema_param=schema,
            structured=structured,
        ):
            if event.get("type") == "error":
                yield json.dumps(event) + "\n"
                return
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
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
