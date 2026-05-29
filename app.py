"""
app.py — Gradio UI for Zoomify.

Two-column layout:
- LEFT: a chat interface. Messages stack above; the input at the bottom is a
  multimodal textbox with a "+" button to attach an image and a send button.
  Only image files are accepted. A one-click example (the Aviva electrical
  single-line diagram) is provided for free experimentation.
- RIGHT: the image history DAG, drawn as a vertical tree (root at top, zoom
  branches flowing downward), with the current node highlighted.

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
from openai import OpenAI
from PIL import Image

from zoomify.agent import DEFAULT_MODEL, SYSTEM_PROMPT, build_user_turn, iter_agent
from zoomify.tools import ImageState, encode_image

load_dotenv()

EXAMPLE_IMAGE = os.path.join("Example Files", "Aviva", "106 Aviva -Electrical - SLD .png")
DEFAULT_PROMPT = "Extract the key information from this image; zoom in to read any small text."


def _has_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


# --------------------------------------------------------------- tree render

_TREE_CSS = """
<style>
.dag { font-family: ui-sans-serif, system-ui, sans-serif; font-size: 12px; }
.dag ul { list-style: none; margin: 0; padding-left: 20px; border-left: 2px solid #d4d4d8; }
.dag > ul { padding-left: 0; border-left: none; }
.dag li { margin: 8px 0; position: relative; }
.dag .node { display: inline-flex; align-items: center; gap: 8px; padding: 5px 9px;
  border: 1px solid #d4d4d8; border-radius: 10px; background: #fafafa; }
.dag .node.current { border-color: #f59e0b; background: #fff7ed;
  box-shadow: 0 0 0 2px #fcd34d; }
.dag .node img.thumb { height: 60px; border: 1px solid #cbd5e1; border-radius: 4px;
  display: block; cursor: zoom-in; transition: box-shadow .12s ease; }
.dag .node img.thumb:hover { box-shadow: 0 0 0 2px #60a5fa; }
.dag .node .lbl { line-height: 1.25; }
.dag .node .lbl b { color: #334155; }
.dag .node.current .lbl b { color: #b45309; }
.dag .hint { color: #64748b; font-style: italic; }

/* node preview modal */
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


def _render_node(state: ImageState, nid: int) -> str:
    n = state.nodes[nid]
    cur = " current" if nid == state.current_id else ""
    thumb = encode_image(n.image, max_side=160, fmt="JPEG")
    preview = encode_image(n.image, max_side=1100, fmt="JPEG")
    label = html.escape(n.label)
    cap = html.escape(f"#{n.id} · {n.label}")
    marker = " ◀ current" if nid == state.current_id else ""
    onclick = (
        "var m=document.getElementById('zmodal');"
        "document.getElementById('zmodal-img').src=this.dataset.full;"
        "document.getElementById('zmodal-cap').textContent=this.dataset.cap;"
        "m.style.display='flex';"
    )
    out = (
        f'<li><div class="node{cur}">'
        f'<img class="thumb" src="{thumb}" data-full="{preview}" data-cap="{cap}" '
        f'alt="node {n.id}" title="Click to preview" onclick="{onclick}"/>'
        f'<span class="lbl"><b>#{n.id}</b> {label}{marker}</span>'
        f'</div>'
    )
    if n.children:
        out += "<ul>" + "".join(_render_node(state, c) for c in n.children) + "</ul>"
    out += "</li>"
    return out


def render_tree(state: ImageState | None) -> str:
    if state is None or not state.nodes:
        return _TREE_CSS + '<div class="dag"><p class="hint">Upload an image to start building the zoom tree.</p></div>'
    body = _render_node(state, state.root_id)
    return _TREE_CSS + f'<div class="dag"><ul>{body}</ul></div>' + _MODAL_HTML


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

def respond(message, chat_history, conv_messages, image_state):
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
                "⚠️ No `OPENAI_API_KEY` found. Add it to a `.env` file (see `.env.example`) and restart."},
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
        client = OpenAI()
        model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        gen = iter_agent(conv_messages, image_state, client, model)
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
            "zoom **tree**.\n\n"
            f"**Model:** `{os.environ.get('OPENAI_MODEL', DEFAULT_MODEL)}` "
            f"· {'✅ API key detected' if _has_key() else '⚠️ set OPENAI_API_KEY in .env'}"
        )

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
                tree = gr.HTML(value=render_tree(None), label="Zoom tree (DAG)")

        outputs = [chatbot, conv_messages, image_state, tree, chat_input, stop_btn]
        submit_event = chat_input.submit(
            respond,
            inputs=[chat_input, chatbot, conv_messages, image_state],
            outputs=outputs,
        )
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
