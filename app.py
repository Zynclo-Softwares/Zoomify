"""
app.py — Gradio UI for Zoomify.

Two-column layout:
- LEFT: a chat interface. Messages stack above; the input at the bottom is a
  multimodal textbox with a "+" button to attach an image and a send button.
  Only image files are accepted. A one-click example (the Aviva electrical
  single-line diagram) is provided for free experimentation.
- RIGHT: the zoom **breadcrumb trail** — root plus each stack step, collapsing on undo.

Zoomify is a general-purpose detail extractor for any hard-to-read image
(high-resolution, very large, very long/wide, dense, or tiny-font) — maps,
diagrams, screenshots, scrolling captures, scans, dashboards, and more.

Run:
    uv run python app.py
"""

from __future__ import annotations

import html
import os

import gradio as gr
from dotenv import load_dotenv
from PIL import Image

from zoomify.agent import SYSTEM_PROMPT, build_user_turn, iter_agent
from zoomify.config import DEFAULT_MODEL, api_key, has_api_key, make_client
from zoomify.openrouter_models import model_dropdown_update, resolve_model
from zoomify.tools import ImageState, encode_image

load_dotenv()

EXAMPLE_IMAGE = os.path.join("Example Files", "Aviva", "106 Aviva -Electrical - SLD .png")
DEFAULT_PROMPT = "Extract the key information from this image; zoom in to read any small text."


def _has_key() -> bool:
    return has_api_key()


def initial_model_dropdown() -> tuple[list[str], str]:
    """Return (choices, value) for constructing the Dropdown at build time."""
    upd = model_dropdown_update(api_key=api_key())
    return upd["choices"], upd["value"]


def refresh_model_dropdown():
    """Reload models from OpenRouter into the dropdown."""
    upd = model_dropdown_update(api_key=api_key(), force_refresh=True)
    return gr.update(choices=upd["choices"], value=upd["value"])


# --------------------------------------------------------------- trail render

_TRAIL_CSS = """
<style>
.trail { font-family: ui-sans-serif, system-ui, sans-serif; font-size: 12px; }
.trail .hint { color: #64748b; font-style: italic; margin-bottom: 10px; }
.trail .crumbs { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.trail .crumb { display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px;
  border: 1px solid #d4d4d8; border-radius: 10px; background: #fafafa; width: fit-content;
  max-width: 100%; box-sizing: border-box; }
.trail .crumb.current { border-color: #f59e0b; background: #fff7ed;
  box-shadow: 0 0 0 2px #fcd34d; }
.trail .crumb img.thumb { height: 56px; width: auto; border: 1px solid #cbd5e1; border-radius: 4px;
  display: block; cursor: zoom-in; flex-shrink: 0; object-fit: contain; }
.trail .crumb img.thumb:hover { box-shadow: 0 0 0 2px #60a5fa; }
.trail .crumb .lbl { line-height: 1.25; color: #334155; font-size: 12px; white-space: nowrap; }
.trail .crumb .lbl b { color: #334155; }
.trail .crumb.current .lbl { color: #92400e; }
.trail .crumb.current .lbl b { color: #b45309; }
.trail .sep { color: #94a3b8; padding-left: 20px; font-size: 11px; }

.zmodal { position: fixed; inset: 0; z-index: 9999; display: none;
  align-items: center; justify-content: center; }
.zmodal .zbackdrop { position: absolute; inset: 0; background: rgba(15,23,42,0.72); }
.zmodal .zcontent { position: relative; max-width: 92vw; max-height: 92vh;
  background: #fff; padding: 10px; border-radius: 12px;
  box-shadow: 0 12px 48px rgba(0,0,0,0.45); }
.zmodal .zcontent img { max-width: 88vw; max-height: 80vh; display: block; border-radius: 6px; }
.zmodal .zcap { font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px;
  color: #334155; margin-top: 8px; text-align: center; }
.zmodal .zclose { position: absolute; top: -14px; right: -14px; width: 32px; height: 32px;
  border-radius: 50%; border: none; background: #0f172a; color: #fff; font-size: 20px;
  line-height: 1; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.35); }
.zmodal .zclose:hover { background: #334155; }
</style>
"""

_MODAL_HTML = """
<div id="zmodal" class="zmodal">
  <div class="zbackdrop" onclick="document.getElementById('zmodal').style.display='none'"></div>
  <div class="zcontent">
    <button class="zclose" title="Close" aria-label="Close"
      onclick="document.getElementById('zmodal').style.display='none'">&times;</button>
    <img id="zmodal-img" src="" alt="node preview"/>
    <div class="zcap" id="zmodal-cap"></div>
  </div>
</div>
"""


def _render_crumb(label: str, depth: int, img: Image.Image, current: bool) -> str:
    cur = " current" if current else ""
    thumb = encode_image(img, max_side=120, fmt="JPEG")
    preview = encode_image(img, max_side=1100, fmt="JPEG")
    safe_label = html.escape(label)
    cap = html.escape(f"depth {depth} · {label}")
    marker = " ◀ current" if current else ""
    onclick = (
        "var m=document.getElementById('zmodal');"
        "document.getElementById('zmodal-img').src=this.dataset.full;"
        "document.getElementById('zmodal-cap').textContent=this.dataset.cap;"
        "m.style.display='flex';"
    )
    return (
        f'<div class="crumb{cur}">'
        f'<img class="thumb" src="{thumb}" data-full="{preview}" data-cap="{cap}" '
        f'alt="depth {depth}" title="Click to preview" onclick="{onclick}"/>'
        f'<span class="lbl"><b>#{depth}</b> {safe_label}{marker}</span>'
        f'</div>'
    )


def render_trail(state: ImageState | None) -> str:
    if state is None:
        return _TRAIL_CSS + '<div class="trail"><p class="hint">Upload an image to start the zoom trail.</p></div>'
    labels = state.checkpoint_labels()
    crumbs = []
    for depth, label in enumerate(labels):
        img = state.render_prefix(depth)
        crumbs.append(_render_crumb(label, depth, img, depth == len(labels) - 1))
    body = "".join(crumbs)
    return _TRAIL_CSS + f'<div class="trail"><div class="crumbs">{body}</div></div>' + _MODAL_HTML


# Backward-compatible alias used in tests / handlers.
render_tree = render_trail


# --------------------------------------------------------------- helpers

def _extract_image(files) -> Image.Image | None:
    """Load the first attached file as a PIL image, or return None if there is
    no file / it is not a valid image."""
    if not files:
        return None
    f = files[0]
    path = f.get("path") if isinstance(f, dict) else f
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception:
        return None


# --------------------------------------------------------------- main handler

def respond(message, chat_history, conv_messages, image_state, model=DEFAULT_MODEL):
    """Streaming handler: yields UI updates so the zoom-tree pointer can be
    watched moving through the tree in real time as the agent navigates.

    Each yield is a 6-tuple; the last two entries drive the input box and the
    Stop button: while the agent is working the input is disabled (interactive
    =False) and Stop is enabled, then the reverse once it finishes.
    """
    chat_history = chat_history or []
    message = message or {}
    text = (message.get("text") or "").strip()
    files = message.get("files") or []

    # Input box / Stop button states.
    idle_input = gr.update(value=None, interactive=True)   # cleared + typable
    busy_input = gr.update(value=None, interactive=False)  # cleared + locked
    stop_on = gr.update(interactive=True)
    stop_off = gr.update(interactive=False)

    # A file was attached: it must be a valid image.
    if files:
        img = _extract_image(files)
        if img is None:
            chat_history += [
                {"role": "user", "content": text or "[attachment]"},
                {"role": "assistant", "content": "❌ Only image files are accepted. Please attach a PNG/JPG image."},
            ]
            yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
            return
    else:
        img = None

    if img is None and not text:
        yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
        return

    if not _has_key():
        chat_history += [
            {"role": "user", "content": text or "[uploaded map]"},
            {"role": "assistant", "content":
                "⚠️ No API key found. Set `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`) "
                "in `.env` (see `.env.example`) and restart."},
        ]
        yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
        return

    # A new image starts a fresh session (new tree + new conversation).
    if img is not None:
        prompt = text or DEFAULT_PROMPT
        image_state = ImageState.from_image(img)
        conv_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        conv_messages.append(build_user_turn(prompt, image_state.current))
        chat_history = [{"role": "user", "content": (text + "  \n*(new map uploaded)*") if text else "*(new map uploaded)*"}]
    else:
        if not conv_messages:
            chat_history.append({"role": "user", "content": text})
            chat_history.append({"role": "assistant", "content": "Please attach an image (via the + button) with your first message."})
            yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
            return
        # Start every new query from the ROOT (top) of the zoom tree so the
        # agent navigates top-down instead of resuming from the deep node the
        # previous query left the pointer on. Attach the root image so the
        # model actually sees the full map fresh (it only keeps one image in
        # context); cached branches still make re-zooming instant.
        if image_state is not None:
            image_state.reset_to_root()
            conv_messages.append(build_user_turn(text, image_state.current))
        else:
            conv_messages.append(build_user_turn(text, None))
        chat_history.append({"role": "user", "content": text})

    # Lock input + enable Stop, and show the starting tree immediately.
    yield chat_history, conv_messages, image_state, render_tree(image_state), busy_input, stop_on

    try:
        client = make_client()
        selected = resolve_model(model)
        gen = iter_agent(conv_messages, image_state, client, selected)
        final = ""
        while True:
            try:
                snapshot = next(gen)
            except StopIteration as stop:
                final, _produced, conv_messages = stop.value
                break
            # A tool round completed: the pointer moved -> re-render the tree.
            yield chat_history, conv_messages, image_state, render_tree(snapshot), busy_input, stop_on
    except Exception as e:
        chat_history.append({"role": "assistant", "content": f"❌ Error: {e}"})
        yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
        return

    chat_history.append({"role": "assistant", "content": final})
    # Unlock input + disable Stop.
    yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off


def reset():
    return ([], [], None, render_tree(None),
            gr.update(value=None, interactive=True), gr.update(interactive=False))


def on_stop(chat_history):
    """Stop handler: cancels the running agent (wired via ``cancels``) and
    restores the UI — re-enabling input and disabling Stop."""
    chat_history = chat_history or []
    chat_history.append({"role": "assistant", "content": "⏹ Stopped."})
    return chat_history, gr.update(interactive=True), gr.update(interactive=False)


# --------------------------------------------------------------- UI

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Zoomify — Image Detail Extraction Agent") as demo:
        gr.Markdown(
            "# 🔆 Zoomify — Image Detail Extraction Agent\n"
            "Attach **any hard-to-read image** with the **+** button and ask a question — "
            "high-resolution photos, very long/tall **scrolling screenshots**, dense dashboards "
            "or app UIs, maps & diagrams, scans, spreadsheets, posters. Anything with **tiny "
            "fonts** or small details. The image is auto-gridded, then the agent **zooms** into "
            "cells (with **undo / redo / restore**) to read the detail. The right panel shows the "
            "zoom **trail** (breadcrumb stack).\n\n"
            f"{'✅ API key detected' if _has_key() else '⚠️ set OPENROUTER_API_KEY in .env'}"
        )

        model_choices, model_value = initial_model_dropdown()
        with gr.Row():
            model_dropdown = gr.Dropdown(
                choices=model_choices,
                value=model_value,
                label="Vision model",
                filterable=True,
                allow_custom_value=False,
                scale=4,
            )
            refresh_models_btn = gr.Button("↻ Refresh", scale=1)

        conv_messages = gr.State([])
        image_state = gr.State(None)

        with gr.Row(equal_height=False):
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(label="Conversation", height=560)
                chat_input = gr.MultimodalTextbox(
                    file_types=["image"],
                    sources=["upload"],
                    placeholder="Ask about the image… use + to attach an image (images only).",
                    show_label=False,
                )
                with gr.Row():
                    stop_btn = gr.Button("⏹ Stop", variant="stop", scale=1, interactive=False)
                    reset_btn = gr.Button("Reset session", scale=1)
                gr.Examples(
                    label="Example image (click to load, then Send)",
                    examples=[{"text": DEFAULT_PROMPT, "files": [EXAMPLE_IMAGE]}],
                    inputs=[chat_input],
                )
            with gr.Column(scale=1):
                tree = gr.HTML(value=render_trail(None), label="Zoom trail (stack)")

        outputs = [chatbot, conv_messages, image_state, tree, chat_input, stop_btn]
        submit_event = chat_input.submit(
            respond,
            inputs=[chat_input, chatbot, conv_messages, image_state, model_dropdown],
            outputs=outputs,
        )
        refresh_models_btn.click(refresh_model_dropdown, outputs=model_dropdown)
        # Stop cancels the running agent generator, then restores the UI.
        stop_btn.click(
            on_stop,
            inputs=[chatbot],
            outputs=[chatbot, chat_input, stop_btn],
            cancels=[submit_event],
        )
        reset_btn.click(reset, outputs=outputs)

    return demo


if __name__ == "__main__":
    build_ui().queue().launch(theme=gr.themes.Soft())
