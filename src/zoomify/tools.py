"""
tools.py — zoom tool layer (stack-based zoom path).

Holds the stateful :class:`ImageState`: the opened image is auto-gridded at the
root, and each ``zoom`` **pushes** a recipe step onto a stack. ``undo`` pops the
last step; ``restore`` clears the stack. The current gridded view is rendered
from ``original + path`` on demand (no branching node DAG or stored
intermediates).

Tools (exposed to agents over MCP by :mod:`zoomify.mcp_server`):
- zoom    : push a crop/upscale/re-grid step onto the path.
- undo    : pop the last zoom step.
- redo    : re-push the step last popped by ``undo``.
- restore : clear the path back to the root view.

Each tool returns a text status plus the now-current gridded image.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image

from . import gridder, gridzoom
from .gridder import GridMeta


# Upper bound on the pixel count of one zoomed view. A large selection times a
# large factor would otherwise allocate gigabytes; the factor is lowered to fit.
MAX_ZOOMED_PIXELS = 36_000_000


def _crop_bbox(state: "ImageState", select: str) -> tuple[int, int, int, int]:
    cw, ch = state.content.size
    bbox, _ = gridzoom.selection_bbox(state.meta, select, cw, ch)
    return bbox


def _fit_zoom(state: "ImageState", select: str, zoom: float) -> float:
    """Lower ``zoom`` (never below 1) so the zoomed crop stays within budget."""
    x0, y0, x1, y1 = _crop_bbox(state, select)
    area = max(1, (x1 - x0) * (y1 - y0))
    max_zoom = (MAX_ZOOMED_PIXELS / area) ** 0.5
    return max(1.0, min(zoom, max_zoom))


def _estimate_regrid_cols(state: "ImageState", select: str, zoom: float) -> int:
    """Pick re-grid columns from the post-zoom crop size and parent cell width."""
    x0, y0, x1, y1 = _crop_bbox(state, select)
    nw = max(1, int(round((x1 - x0) * zoom)))
    nh = max(1, int(round((y1 - y0) * zoom)))
    return gridder.auto_grid_cols(nw, nh, parent_cell_w=state.meta.cell_w)


# --------------------------------------------------------------- stack state


@dataclass(frozen=True)
class ZoomStep:
    """One zoom operation relative to the view at its stack depth."""

    select: str
    zoom: float
    regrid_cols: int

    @property
    def label(self) -> str:
        return f"zoom {self.select} {self.zoom:g}x"


@dataclass
class ImageState:
    """Original upload plus a stack of zoom steps; current view is derived."""

    original: Image.Image
    root_meta: GridMeta
    root_image: Image.Image
    root_label: str
    path: list[ZoomStep] = field(default_factory=list)
    _redo: ZoomStep | None = None
    _cached_len: int = -1
    _cached_gridded: Image.Image | None = field(default=None, repr=False)
    _cached_meta: GridMeta | None = field(default=None, repr=False)
    _cached_content: Image.Image | None = field(default=None, repr=False)

    @classmethod
    def from_image(cls, img: Image.Image, cols: int | None = None) -> "ImageState":
        rgb = img.convert("RGB")
        gridded, meta = gridder.apply_grid(rgb, cols=cols)
        label = f"grid {meta.ncols}x{meta.nrows}"
        return cls(original=rgb, root_meta=meta, root_image=gridded, root_label=label)

    def _invalidate(self) -> None:
        self._cached_len = -1
        self._cached_gridded = None
        self._cached_meta = None
        self._cached_content = None

    def _ensure_rendered(self) -> None:
        if self._cached_len == len(self.path) and self._cached_gridded is not None:
            return
        gridded, meta, content = gridzoom.render_at_path(
            self.original,
            self.root_meta,
            self.root_image,
            self.path,
        )
        self._cached_gridded = gridded
        self._cached_meta = meta
        self._cached_content = content
        self._cached_len = len(self.path)

    @property
    def current(self) -> Image.Image:
        self._ensure_rendered()
        assert self._cached_gridded is not None
        return self._cached_gridded

    @property
    def meta(self) -> GridMeta:
        self._ensure_rendered()
        assert self._cached_meta is not None
        return self._cached_meta

    @property
    def content(self) -> Image.Image:
        self._ensure_rendered()
        assert self._cached_content is not None
        return self._cached_content

    @property
    def depth(self) -> int:
        return len(self.path)

    def checkpoint_labels(self) -> list[str]:
        return [self.root_label, *(s.label for s in self.path)]

    def render_prefix(self, depth: int) -> Image.Image:
        """Gridded image at stack depth ``depth`` (0 = root)."""
        depth = max(0, min(depth, len(self.path)))
        gridded, _, _ = gridzoom.render_at_path(
            self.original,
            self.root_meta,
            self.root_image,
            self.path[:depth],
        )
        return gridded

    def reset_to_root(self) -> None:
        """Clear the zoom stack."""
        self.path.clear()
        self._redo = None
        self._invalidate()


# --------------------------------------------------------------- encoding


def encode_view(
    img: Image.Image, max_side: int = 1568, max_png_bytes: int = 900_000
) -> tuple[bytes, str]:
    """Encode a gridded view for an MCP image result: ``(data, format)``.

    Views are downscaled to ``max_side`` (what vision models actually ingest).
    PNG keeps line art and small text crisp; photographic views that would be
    too heavy as PNG fall back to JPEG.
    """
    work = img.convert("RGB")
    w, h = work.size
    scale = max(w, h) / max_side
    if scale > 1:
        work = work.resize((max(1, int(w / scale)), max(1, int(h / scale))), Image.LANCZOS)
    buf = io.BytesIO()
    work.save(buf, format="PNG", optimize=True)
    if buf.tell() <= max_png_bytes:
        return buf.getvalue(), "png"
    buf = io.BytesIO()
    work.save(buf, format="JPEG", quality=88)
    return buf.getvalue(), "jpeg"


# --------------------------------------------------------------- dispatch


@dataclass
class ToolResult:
    text: str
    image: Image.Image | None = None


def _pos(state: ImageState) -> str:
    n = len(state.checkpoint_labels())
    return f"[depth {state.depth}, {n} checkpoint(s)]"


def run_tool(name: str, args: dict, state: ImageState) -> ToolResult:
    """Execute a tool call against the shared :class:`ImageState`."""
    if name == "zoom":
        select = args.get("select")
        if not select:
            return ToolResult(
                text="Missing 'select'. Provide cells/regions like '2C' or '1-3-B-E'."
            )
        zoom = max(1.0, min(8.0, float(args.get("zoom", 3) or 3)))

        try:
            gridzoom.parse_selection(select, state.meta.ncols, state.meta.nrows)
        except ValueError as e:
            return ToolResult(text=f"zoom error: {e}")

        requested = zoom
        zoom = round(_fit_zoom(state, select, zoom), 2)

        raw_cols = args.get("regrid_cols")
        if raw_cols is None or raw_cols == "":
            regrid_cols = _estimate_regrid_cols(state, select, zoom)
        else:
            regrid_cols = max(2, min(30, int(raw_cols)))

        step = ZoomStep(select=select, zoom=zoom, regrid_cols=regrid_cols)
        state.path.append(step)
        state._redo = None
        state._invalidate()
        state._ensure_rendered()

        note = (
            f" (lowered from {requested:g}x — the selection is large; pick fewer cells "
            "to magnify further)"
            if zoom < requested
            else ""
        )
        msg = (
            f"Zoomed selection {select!r} by {zoom:g}x{note} (stack depth {state.depth}). "
            f"Pushed '{step.label}'. `zoom` again to go deeper, or `undo` to step back. "
            f"{_pos(state)} Image shown next."
        )
        return ToolResult(text=msg, image=state.current)

    if name == "undo":
        if not state.path:
            return ToolResult(
                text=f"Already at the root; nothing to undo. {_pos(state)}", image=state.current
            )
        state._redo = state.path.pop()
        state._invalidate()
        label = state._redo.label
        return ToolResult(
            text=f"Popped '{label}'. Now at depth {state.depth}. {_pos(state)} Image shown next.",
            image=state.current,
        )

    if name == "redo":
        if state._redo is None:
            return ToolResult(text=f"No zoom step to redo. {_pos(state)}", image=state.current)
        step = state._redo
        state.path.append(step)
        state._redo = None
        state._invalidate()
        return ToolResult(
            text=f"Redid '{step.label}'. Depth {state.depth}. {_pos(state)} Image shown next.",
            image=state.current,
        )

    if name == "restore":
        if not state.path:
            return ToolResult(
                text=f"Already at the root '{state.root_label}'. {_pos(state)} Image shown next.",
                image=state.current,
            )
        state.reset_to_root()
        state._ensure_rendered()
        return ToolResult(
            text=f"Cleared stack; back at root '{state.root_label}'. {_pos(state)} Image shown next.",
            image=state.current,
        )

    return ToolResult(text=f"Unknown tool: {name}")
