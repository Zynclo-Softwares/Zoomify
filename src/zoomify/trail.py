"""Zoom breadcrumb trail HTML renderer (shared by Gradio and FastAPI/React)."""

from __future__ import annotations

import html

from PIL import Image

from .tools import ImageState, encode_image

_TRAIL_CSS = """
<style>
.trail { font-family: ui-sans-serif, system-ui, sans-serif; font-size: 11px; color: #e2e8f0;
  display: flex; flex-direction: column; justify-content: flex-end; min-height: 100%; box-sizing: border-box; }
.trail .hint { color: #64748b; font-style: italic; margin-bottom: 10px; }
.trail .crumbs { display: flex; flex-direction: column-reverse; align-items: stretch; gap: 4px;
  width: 100%; }
.trail .crumb { display: flex; align-items: center; gap: 6px; padding: 5px 8px;
  border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 8px;
  background: rgba(17, 24, 39, 0.75); width: 100%;
  max-width: 100%; box-sizing: border-box;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.22); }
.trail .crumb.current { border-color: rgba(0, 85, 255, 0.55); background: rgba(0, 85, 255, 0.1);
  box-shadow: 0 -6px 16px rgba(0, 85, 255, 0.18), 0 0 0 1px rgba(0, 85, 255, 0.25);
  z-index: 1; position: relative; }
.trail .crumb img.thumb { height: 44px; width: auto; border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 4px; display: block; cursor: zoom-in; flex-shrink: 0; object-fit: contain; }
.trail .crumb img.thumb:hover { box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.55); }
.trail .crumb .lbl { line-height: 1.25; color: #cbd5e1; font-size: 11px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.trail .crumb .lbl b { color: #f1f5f9; }
.trail .crumb.current .lbl { color: #93c5fd; }
.trail .crumb.current .lbl b { color: #bfdbfe; }
</style>
"""


def _render_crumb(label: str, depth: int, img: Image.Image, current: bool) -> str:
    cur = " current" if current else ""
    thumb = encode_image(img, max_side=88, fmt="JPEG")
    preview = encode_image(img, max_side=1100, fmt="JPEG")
    safe_label = html.escape(label)
    cap = html.escape(f"depth {depth} · {label}")
    return (
        f'<div class="crumb{cur}">'
        f'<img class="thumb" src="{thumb}" data-full="{preview}" data-cap="{cap}" '
        f'alt="depth {depth}" title="Click to preview"/>'
        f'<span class="lbl"><b>#{depth}</b> {safe_label}</span>'
        f"</div>"
    )


def render_trail(state: ImageState | None) -> str:
    if state is None:
        return (
            _TRAIL_CSS
            + '<div class="trail"><p class="hint">Upload an image to start the zoom trail.</p></div>'
        )
    labels = state.checkpoint_labels()
    crumbs = [
        _render_crumb(label, depth, state.render_prefix(depth), depth == len(labels) - 1)
        for depth, label in enumerate(labels)
    ]
    body = "".join(crumbs)
    return _TRAIL_CSS + f'<div class="trail"><div class="crumbs">{body}</div></div>'


render_tree = render_trail
