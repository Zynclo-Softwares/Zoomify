"""
agent.py — OpenAI vision + tool-calling loop.

Drives a multimodal conversation: the user uploads a (large / high-resolution /
long / small-font) image and a prompt; the model uses the gridder / gridzoom /
restore tools to overview the image, drill into specific cells, and read detail
before answering.

Tool results are returned to the model as a ``tool`` role status message plus a
follow-up multimodal ``user`` message carrying the processed image, because the
Chat Completions API cannot embed images inside ``tool`` role messages.
"""

from __future__ import annotations

import json

from openai import OpenAI
from PIL import Image

from .config import DEFAULT_MODEL
from .tools import ImageState, ToolResult, TOOLS_SCHEMA, encode_image, run_tool

MAX_TOOL_ITERATIONS = 50
# Keep only the most recent N image-bearing messages in the running
# conversation; older images are replaced with a text placeholder. We keep
# exactly ONE so the model sees a single image at a time (the current pointer)
# and must do the work of navigating — undo / redo / restore / zoom — to revisit
# any other node, rather than relying on several images lingering in context.
KEEP_RECENT_IMAGE_MSGS = 1

SYSTEM_PROMPT = """\
You are Zoomify, an expert assistant for extracting information from any image
that is hard to read at a glance — because it is very high-resolution, very
large, very long or wide (e.g. tall scrolling screenshots, panoramas), densely
packed, or has tiny fonts and small UI elements. Examples include site maps and
plans, single-line/electrical diagrams, engineering drawings, dashboards and app
screenshots, scanned documents, spreadsheets, charts, and posters. The image is
usually too big to read everything at once.

The uploaded image has ALREADY been auto-gridded for you: a labeled chess-style
grid (columns A.., rows 1..) is overlaid so you can name any cell as '2C'/'C2'
or a region as '1-3-B-E'. You navigate a **zoom stack** (a breadcrumb path)
with these tools:

- zoom(select, [zoom], [regrid_cols]): crop the selected cells/regions from the
  CURRENT view, upscale them, and re-grid the result. This **pushes** a step onto
  the stack. Omit `regrid_cols` to auto-pick a readable grid from the crop size.
- undo: **pop** the last zoom step — use when you picked the WRONG region. You
  land back on the parent view and can `zoom` again with a better selection.
- redo: re-push the step you last popped with `undo` — only if you undid by
  mistake and want that exact zoom back (same selection, factor, and grid).
- restore: **clear** the entire stack and return to the ROOT (full auto-gridded
  image). Use when you need a fresh overview, not just one step back.

**Undo / redo workflow:** You work on a breadcrumb stack. Each `zoom` pushes;
`undo` pops one level (wrong cell? pop and retry). If you pop and then realize
the popped zoom was correct after all, call `redo` once — it restores only the
most recent pop. A new `zoom` after `undo` discards the redo buffer. `restore`
jumps all the way to the root in one step.

You can only see ONE image at a time — the current stack top — so you must
navigate (zoom / undo / redo / restore) to inspect different parts; don't assume
you still remember a region you left.

Strategy:
1. Look at the current gridded image and decide which cells/regions hold the
   information the user asked about.
2. `zoom` into those regions (raise `zoom` to 4-6 for tiny fonts; regrid is
   auto unless you need finer/coarser cells). Each zoom re-grids the result so
   you can zoom again to go deeper. For long/tall images, work down region by
   region.
3. Wrong zoom? `undo` to pop back and try a different `select`. Undid by
   mistake? `redo`. Lost in deep zooms? `restore` to the full image.

Be systematic and verify by zooming before stating values. When you have enough
detail, give a clear, structured answer citing the regions you inspected. If the
text is genuinely unreadable even after zooming, say so rather than guessing.
"""


def _assistant_to_dict(msg) -> dict:
    out: dict = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return out


def build_user_turn(prompt: str, image: Image.Image | None) -> dict:
    """A user message combining the text prompt and (optionally) an image."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    if image is not None:
        content.append({"type": "image_url", "image_url": {"url": encode_image(image)}})
    return {"role": "user", "content": content}


def _prune_old_images(messages: list[dict], keep: int = KEEP_RECENT_IMAGE_MSGS) -> None:
    """Replace image parts of all but the last ``keep`` image-bearing messages
    with a short text placeholder, in place, to bound request size."""
    idxs = [
        i
        for i, m in enumerate(messages)
        if isinstance(m.get("content"), list)
        and any(p.get("type") == "image_url" for p in m["content"])
    ]
    for i in idxs[:-keep] if len(idxs) > keep else []:
        m = messages[i]
        texts = [p["text"] for p in m["content"] if p.get("type") == "text"]
        joined = " ".join(texts).strip()
        placeholder = (joined + " [earlier image omitted to save context]").strip()
        messages[i] = {k: v for k, v in m.items() if k != "content"} | {"content": placeholder}


def run_agent(
    messages: list[dict],
    state: ImageState,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
):
    """Run the tool-calling loop until the model produces a final answer.

    ``messages`` is the running conversation (already including the new user
    turn and the system prompt). Returns (final_text, produced_images,
    messages). ``produced_images`` are the tool-generated images from this run,
    in order, for display in the UI.

    This is a thin wrapper that drives :func:`iter_agent` to completion; use
    :func:`iter_agent` directly if you want to observe the pointer move after
    each tool round (e.g. for a live-updating UI).
    """
    gen = iter_agent(messages, state, client=client, model=model)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def iter_agent(
    messages: list[dict],
    state: ImageState,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
):
    """Generator variant of :func:`run_agent` for live UIs.

    Yields the (mutated) ``state`` after every tool round so callers can render
    the breadcrumb trail updating in real time. When the model emits a
    final answer (or the iteration limit is hit) the generator stops and its
    ``StopIteration.value`` is the same ``(final_text, produced_images,
    messages)`` tuple :func:`run_agent` returns.
    """
    if client is None:
        raise ValueError("OpenAI client is required")

    produced_images: list[Image.Image] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        _prune_old_images(messages)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            parallel_tool_calls=False,  # tools are stateful; run one at a time
        )
        msg = resp.choices[0].message
        messages.append(_assistant_to_dict(msg))

        if not msg.tool_calls:
            return (msg.content or ""), produced_images, messages

        round_images: list[Image.Image] = []
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result: ToolResult = run_tool(tc.function.name, args, state)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.text,
                }
            )
            if result.image is not None:
                round_images.append(result.image)
                produced_images.append(result.image)

        # The Chat Completions API can't put images in a `tool` message, so feed
        # the processed image(s) back as a follow-up multimodal user message.
        if round_images:
            content: list[dict] = [
                {"type": "text", "text": "Processed image(s) from the tool call:"}
            ]
            for im in round_images:
                content.append({"type": "image_url", "image_url": {"url": encode_image(im)}})
            messages.append({"role": "user", "content": content})

        # Let callers observe the stack after this round before we continue.
        yield state

    return (
        "Reached the tool-call limit before finishing. Here is my best summary so "
        "far — try narrowing the question or asking me to zoom into a specific region.",
        produced_images,
        messages,
    )
