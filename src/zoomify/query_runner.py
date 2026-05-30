"""Shared query runner for Gradio and FastAPI (streaming trail + agent)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any

from PIL import Image

from .agent import SYSTEM_PROMPT, build_user_turn, iter_agent
from .config import DEFAULT_MODEL, has_api_key, make_client
from .openrouter_models import resolve_model
from .schema_registry import SchemaResolution, apply_schema_to_agent_config, resolve_schema
from .session import Session
from .tools import ImageState
from .trail import render_trail

DEFAULT_PROMPT = "Extract the key information from this image; zoom in to read any small text."


def load_image_bytes(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGB")


class QueryError(Exception):
    """User-facing query failure."""


def run_query_stream(
    *,
    session: Session,
    query: str,
    image_bytes: bytes | None,
    model: str | None = None,
    schema_param: str | None = None,
    structured: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield SSE-style event dicts: trail, assistant, error, done."""
    if not has_api_key():
        yield {"type": "error", "message": "No API key found. Set OPENROUTER_API_KEY in .env."}
        return

    query = (query or "").strip()
    img: Image.Image | None = None
    if image_bytes:
        try:
            img = load_image_bytes(image_bytes)
        except Exception as exc:
            yield {"type": "error", "message": f"Invalid image: {exc}"}
            return

    if img is None and not query:
        yield {"type": "error", "message": "Provide a query and/or one image."}
        return

    resolution: SchemaResolution
    try:
        resolution = resolve_schema(
            schema_param=schema_param,
            image=img,
            structured=structured,
        )
    except ValueError as exc:
        yield {"type": "error", "message": str(exc)}
        return

    schema_config = apply_schema_to_agent_config(resolution)
    selected_model = resolve_model(model or DEFAULT_MODEL)

    if img is not None:
        prompt = query or DEFAULT_PROMPT
        session.image_state = ImageState.from_image(img)
        session.conv_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        session.conv_messages.append(build_user_turn(prompt, session.image_state.current))
        user_label = (query + " *(new image)*") if query else "*(new image uploaded)*"
        yield {"type": "user", "content": user_label}
    else:
        if not session.conv_messages or session.image_state is None:
            yield {"type": "error", "message": "Upload an image before sending follow-up queries."}
            return
        session.image_state.reset_to_root()
        session.conv_messages.append(build_user_turn(query, session.image_state.current))
        yield {"type": "user", "content": query}

    yield {
        "type": "schema",
        "structured": schema_config["structured"],
        "schema_id": schema_config["schema_id"],
        "source": schema_config["source"],
    }
    yield {"type": "trail", "html": render_trail(session.image_state)}

    try:
        client = make_client()
        gen = iter_agent(session.conv_messages, session.image_state, client, selected_model)
        final = ""
        while True:
            try:
                snapshot = next(gen)
            except StopIteration as stop:
                final, _produced, session.conv_messages = stop.value
                break
            yield {"type": "trail", "html": render_trail(snapshot)}
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
        return

    yield {"type": "assistant", "content": final}
    yield {"type": "trail", "html": render_trail(session.image_state)}
    yield {"type": "done"}
