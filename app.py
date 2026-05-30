"""
app.py — Gradio UI for Zoomify (legacy; prefer ``uv run uvicorn server:app`` + React).

Two-column layout:
- LEFT: chat interface
- RIGHT: zoom breadcrumb trail

Run:
    uv run python app.py
"""

from __future__ import annotations

import os

import gradio as gr
from dotenv import load_dotenv

from zoomify.agent import SYSTEM_PROMPT, build_user_turn, iter_agent
from zoomify.config import DEFAULT_MODEL, api_key, has_api_key, make_client
from zoomify.openrouter_models import model_dropdown_update, resolve_model
from zoomify.query_runner import DEFAULT_PROMPT
from zoomify.tools import ImageState
from zoomify.trail import render_trail, render_tree

load_dotenv()

EXAMPLE_IMAGE = os.path.join("Example Files", "Aviva", "106 Aviva -Electrical - SLD .png")


def _has_key() -> bool:
    return has_api_key()


def initial_model_dropdown() -> tuple[list[str], str]:
    upd = model_dropdown_update(api_key=api_key())
    return upd["choices"], upd["value"]


def refresh_model_dropdown():
    upd = model_dropdown_update(api_key=api_key(), force_refresh=True)
    return gr.update(choices=upd["choices"], value=upd["value"])


def _extract_image(files):
    if not files:
        return None
    from PIL import Image

    f = files[0]
    path = f.get("path") if isinstance(f, dict) else f
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception:
        return None


def respond(message, chat_history, conv_messages, image_state, model=DEFAULT_MODEL):
    chat_history = chat_history or []
    message = message or {}
    text = (message.get("text") or "").strip()
    files = message.get("files") or []

    idle_input = gr.update(value=None, interactive=True)
    busy_input = gr.update(value=None, interactive=False)
    stop_on = gr.update(interactive=True)
    stop_off = gr.update(interactive=False)

    if files:
        img = _extract_image(files)
        if img is None:
            chat_history += [
                {"role": "user", "content": text or "[attachment]"},
                {"role": "assistant", "content": "❌ Only image files are accepted."},
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
            {"role": "assistant", "content": "⚠️ Set OPENROUTER_API_KEY in `.env` and restart."},
        ]
        yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
        return

    if img is not None:
        prompt = text or DEFAULT_PROMPT
        image_state = ImageState.from_image(img)
        conv_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        conv_messages.append(build_user_turn(prompt, image_state.current))
        chat_history = [{"role": "user", "content": (text + "  \n*(new map uploaded)*") if text else "*(new map uploaded)*"}]
    else:
        if not conv_messages:
            chat_history.append({"role": "user", "content": text})
            chat_history.append({"role": "assistant", "content": "Please attach an image with your first message."})
            yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
            return
        if image_state is not None:
            image_state.reset_to_root()
            conv_messages.append(build_user_turn(text, image_state.current))
        else:
            conv_messages.append(build_user_turn(text, None))
        chat_history.append({"role": "user", "content": text})

    yield chat_history, conv_messages, image_state, render_tree(image_state), busy_input, stop_on

    try:
        client = make_client()
        gen = iter_agent(conv_messages, image_state, client, resolve_model(model))
        final = ""
        while True:
            try:
                snapshot = next(gen)
            except StopIteration as stop:
                final, _produced, conv_messages = stop.value
                break
            yield chat_history, conv_messages, image_state, render_tree(snapshot), busy_input, stop_on
    except Exception as e:
        chat_history.append({"role": "assistant", "content": f"❌ Error: {e}"})
        yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off
        return

    chat_history.append({"role": "assistant", "content": final})
    yield chat_history, conv_messages, image_state, render_tree(image_state), idle_input, stop_off


def reset():
    return ([], [], None, render_trail(None), gr.update(value=None, interactive=True), gr.update(interactive=False))


def on_stop(chat_history):
    chat_history = chat_history or []
    chat_history.append({"role": "assistant", "content": "⏹ Stopped."})
    return chat_history, gr.update(interactive=True), gr.update(interactive=False)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Zoomify — Image Detail Extraction Agent") as demo:
        gr.Markdown(
            "# 🔆 Zoomify (Gradio)\n"
            "Prefer the React UI: `uv run uvicorn server:app --reload`\n\n"
            f"{'✅ API key detected' if _has_key() else '⚠️ set OPENROUTER_API_KEY in .env'}"
        )
        model_choices, model_value = initial_model_dropdown()
        with gr.Row():
            model_dropdown = gr.Dropdown(
                choices=model_choices, value=model_value, label="Vision model",
                filterable=True, allow_custom_value=False, scale=4,
            )
            refresh_models_btn = gr.Button("↻ Refresh", scale=1)
        conv_messages = gr.State([])
        image_state = gr.State(None)
        with gr.Row(equal_height=False):
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(label="Conversation", height=560)
                chat_input = gr.MultimodalTextbox(
                    file_types=["image"], sources=["upload"],
                    placeholder="Ask about the image…", show_label=False,
                )
                with gr.Row():
                    stop_btn = gr.Button("⏹ Stop", variant="stop", scale=1, interactive=False)
                    reset_btn = gr.Button("Reset session", scale=1)
                gr.Examples(
                    label="Example image",
                    examples=[{"text": DEFAULT_PROMPT, "files": [EXAMPLE_IMAGE]}],
                    inputs=[chat_input],
                )
            with gr.Column(scale=1):
                tree = gr.HTML(value=render_trail(None), label="Zoom trail")
        outputs = [chatbot, conv_messages, image_state, tree, chat_input, stop_btn]
        submit_event = chat_input.submit(
            respond,
            inputs=[chat_input, chatbot, conv_messages, image_state, model_dropdown],
            outputs=outputs,
        )
        refresh_models_btn.click(refresh_model_dropdown, outputs=model_dropdown)
        stop_btn.click(on_stop, inputs=[chatbot], outputs=[chatbot, chat_input, stop_btn], cancels=[submit_event])
        reset_btn.click(reset, outputs=outputs)
    return demo


if __name__ == "__main__":
    build_ui().queue().launch(theme=gr.themes.Soft())
