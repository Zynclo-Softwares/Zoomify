"""
tools.py — agent tool layer (stack-based zoom path).

Holds the stateful :class:`ImageState`: the upload is auto-gridded at the root,
and each ``zoom`` **pushes** a recipe step onto a stack. ``undo`` pops the last
step; ``restore`` clears the stack. The current gridded view is rendered from
``original + path`` on demand (no branching node DAG or stored intermediates).

Tools (OpenAI function-calling):
- zoom    : push a crop/upscale/re-grid step onto the path.
- undo    : pop the last zoom step.
- redo    : re-push the step last popped by ``undo``.
- restore : clear the path back to the root view.

Each tool returns a text status (for the ``tool`` role message) and the now
current image (for a follow-up multimodal ``user`` message so the vision model
can actually see it).
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field

from PIL import Image

from . import gridder, gridzoom
from .gridder import GridMeta


def _estimate_regrid_cols(state: "ImageState", select: str, zoom: float) -> int:
    """Pick re-grid columns from the post-zoom crop size and parent cell width."""
    cw, ch = state.content.size
    bbox, _ = gridzoom.selection_bbox(state.meta, select, cw, ch)
    x0, y0, x1, y1 = bbox
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
            self.original, self.root_meta, self.root_image, self.path,
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
            self.original, self.root_meta, self.root_image, self.path[:depth],
        )
        return gridded

    def reset_to_root(self) -> None:
        """Clear the zoom stack (called at the start of each new user query)."""
        self.path.clear()
        self._redo = None
        self._invalidate()


# --------------------------------------------------------------- encoding

def encode_image(img: Image.Image, max_side: int = 1536, fmt: str = "PNG") -> str:
    """Return a base64 data URI, downscaled for transport / thumbnails."""
    work = img.convert("RGB")
    w, h = work.size
    scale = max(w, h) / max_side
    if scale > 1:
        work = work.resize((max(1, int(w / scale)), max(1, int(h / scale))), Image.LANCZOS)
    buf = io.BytesIO()
    work.save(buf, format=fmt)
    mime = "jpeg" if fmt.upper() in ("JPG", "JPEG") else fmt.lower()
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/{mime};base64,{b64}"


# --------------------------------------------------------------- schemas

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "zoom",
            "description": (
                "Crop a cell selection from the CURRENT gridded image, upscale "
                "it, and re-overlay a fresh labeled grid so you can read small "
                "fonts and drill deeper. The selection refers to the column "
                "letters (A, B, ...) and row numbers (1, 2, ...) on the current "
                "image. This pushes a new step onto the zoom stack; use `undo` "
                "to pop back if you picked the wrong region."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "select": {
                        "type": "string",
                        "description": (
                            "Cells/regions to zoom into, referencing the current "
                            "grid labels. Examples: '2C' or 'C2' (one cell), "
                            "'1C,3B,4C' (discrete cells), '1-3-B-E' (rectangle "
                            "rows 1-3 x cols B-E), '1-2-A-F, 3-5-G-J' (multiple "
                            "regions). The crop is the union bounding box."
                        ),
                    },
                    "zoom": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 8,
                        "description": "Upscale factor for the crop (default 3). "
                                       "Use higher (4-6) for tiny fonts.",
                    },
                    "regrid_cols": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 30,
                        "description": "Columns for the fresh grid on the zoomed "
                                       "crop. Omit to auto-pick from crop size "
                                       "(~120px cells, similar to the parent view).",
                    },
                },
                "required": ["select"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo",
            "description": (
                "Pop the last zoom step and return to the previous view. Use "
                "when your latest zoom targeted the wrong cells — you can "
                "immediately try a different `select` from that parent view."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "redo",
            "description": (
                "Re-push the zoom step you most recently popped with `undo`. "
                "Use only if you undid by mistake and want that zoom back "
                "without re-entering the selection."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restore",
            "description": (
                "Clear the zoom stack and return to the ROOT (full auto-gridded "
                "image)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


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
            return ToolResult(text="Missing 'select'. Provide cells/regions like '2C' or '1-3-B-E'.")
        zoom = max(1.0, min(8.0, float(args.get("zoom", 3) or 3)))

        try:
            gridzoom.parse_selection(select, state.meta.ncols, state.meta.nrows)
        except ValueError as e:
            return ToolResult(text=f"zoom error: {e}")

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

        msg = (
            f"Zoomed selection {select!r} by {zoom:g}x (stack depth {state.depth}). "
            f"Pushed '{step.label}'. `zoom` again to go deeper, or `undo` to step back. "
            f"{_pos(state)} Image shown next."
        )
        return ToolResult(text=msg, image=state.current)

    if name == "undo":
        if not state.path:
            return ToolResult(text=f"Already at the root; nothing to undo. {_pos(state)}",
                              image=state.current)
        state._redo = state.path.pop()
        state._invalidate()
        label = state._redo.label
        return ToolResult(
            text=f"Popped '{label}'. Now at depth {state.depth}. {_pos(state)} Image shown next.",
            image=state.current,
        )

    if name == "redo":
        if state._redo is None:
            return ToolResult(text=f"No zoom step to redo. {_pos(state)}",
                              image=state.current)
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
