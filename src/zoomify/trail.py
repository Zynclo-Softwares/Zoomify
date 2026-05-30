"""Zoom breadcrumb trail HTML renderer (shared by Gradio and FastAPI/React)."""

from __future__ import annotations

import html

from PIL import Image

from .tools import ImageState, encode_image

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
    crumbs = [_render_crumb(label, depth, state.render_prefix(depth), depth == len(labels) - 1)
              for depth, label in enumerate(labels)]
    body = "".join(crumbs)
    return _TRAIL_CSS + f'<div class="trail"><div class="crumbs">{body}</div></div>' + _MODAL_HTML


render_tree = render_trail
