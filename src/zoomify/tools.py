"""
tools.py — agent tool layer (branching, cached image DAG).

Holds the stateful :class:`ImageState`, which is a **tree / DAG of images**: the
root is the auto-gridded upload, and every ``zoom`` creates (or reuses) a child
node. A movable ``current`` pointer marks the image being processed. Because the
chess-grid selections are finite, identical zooms from the same node are
**cached**: re-selecting a region just jumps the pointer to the existing child
instead of recomputing.

Tools (OpenAI function-calling):
- zoom    : crop + upscale + re-grid the current image; branch to a (new or
            cached) child node and make it current.
- undo    : move the pointer to the PARENT node.
- redo    : move the pointer forward to the child you last backed out of.
- restore : jump the pointer back to the ROOT (full auto-gridded map).

Each tool returns a text status (for the ``tool`` role message) and the now
current image (for a follow-up multimodal ``user`` message so the vision model
can actually see it).
"""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, field

from PIL import Image

from . import gridder, gridzoom
from .gridder import GridMeta

DEFAULT_GRID_COLS = 10


# --------------------------------------------------------------- tree state

@dataclass
class Node:
    """One image in the DAG."""

    id: int
    parent: int | None
    image: Image.Image
    meta: GridMeta
    label: str
    content: Image.Image                   # ungridded inner content for clean zoom crops
    action_key: str | None = None          # normalized action that created it
    children: list[int] = field(default_factory=list)


def _normalize_action(rects, zoom: float, regrid_cols: int) -> str:
    """Canonical key from parsed cell-rects so equivalent selections (e.g.
    '1-2-A-C' and 'A-C-1-2', or '2C' and 'C2') hit the same cache entry."""
    canon = sorted(tuple(r) for r in rects)
    return f"zoom|{canon}|z{zoom:g}|g{regrid_cols}"


@dataclass
class ImageState:
    """A branching, cached DAG of gridded images with a movable pointer."""

    original: Image.Image
    nodes: dict[int, Node] = field(default_factory=dict)
    root_id: int = 0
    current_id: int = 0
    _next_id: int = 1
    # parent_id -> child_id last entered, so `redo` can return there.
    redo_target: dict[int, int] = field(default_factory=dict)

    @classmethod
    def from_image(cls, img: Image.Image, cols: int = DEFAULT_GRID_COLS) -> "ImageState":
        rgb = img.convert("RGB")
        gridded, meta = gridder.apply_grid(rgb, cols=cols)
        root = Node(id=0, parent=None, image=gridded, meta=meta,
                    label=f"grid {meta.ncols}x{meta.nrows}", content=rgb)
        st = cls(original=rgb, nodes={0: root}, root_id=0, current_id=0, _next_id=1)
        return st

    # -- convenience -----------------------------------------------------
    @property
    def current(self) -> Image.Image:
        return self.nodes[self.current_id].image

    @property
    def meta(self) -> GridMeta:
        return self.nodes[self.current_id].meta

    def _add_child(self, parent_id: int, image: Image.Image, meta: GridMeta,
                   content: Image.Image, label: str, action_key: str) -> int:
        nid = self._next_id
        self._next_id += 1
        self.nodes[nid] = Node(id=nid, parent=parent_id, image=image, meta=meta,
                               label=label, content=content, action_key=action_key)
        self.nodes[parent_id].children.append(nid)
        return nid

    def find_child(self, parent_id: int, action_key: str) -> int | None:
        for cid in self.nodes[parent_id].children:
            if self.nodes[cid].action_key == action_key:
                return cid
        return None

    def reset_to_root(self) -> None:
        """Move the pointer back to the ROOT of the tree.

        Called at the start of every new user query so navigation always
        begins top-down from the full auto-gridded map. Resuming from wherever
        the previous query left the pointer (deep in the tree) forces slow
        bottom-up traversal and is harder for the model to reason about; the
        existing branches stay cached, so re-zooming is still instant.
        """
        self.current_id = self.root_id

    def depth(self, node_id: int) -> int:
        d = 0
        n = self.nodes[node_id]
        while n.parent is not None:
            d += 1
            n = self.nodes[n.parent]
        return d


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
                "image. This branches to a child image in the history tree and "
                "makes it current; you can `undo` to go back to the parent and "
                "try a different region."
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
                        "description": "Columns for the fresh grid drawn on the "
                                       "zoomed crop (default 10).",
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
                "Move the pointer to the PARENT image (one step less zoomed). "
                "Use this when a zoom selected the wrong region so you can pick a "
                "different one from the previous view (creating a new branch)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "redo",
            "description": (
                "Move the pointer FORWARD again to the child image you most "
                "recently backed out of with `undo` (if you have not zoomed "
                "somewhere else since)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restore",
            "description": (
                "Jump the pointer back to the ROOT of the tree: the original "
                "full map as it was first auto-gridded. Use this to begin a "
                "fresh drill-down from the whole map."
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
    n = state.nodes[state.current_id]
    return f"[node #{n.id}, depth {state.depth(n.id)}, {len(state.nodes)} total]"


def run_tool(name: str, args: dict, state: ImageState) -> ToolResult:
    """Execute a tool call against the shared :class:`ImageState`."""
    if name == "zoom":
        select = args.get("select")
        if not select:
            return ToolResult(text="Missing 'select'. Provide cells/regions like '2C' or '1-3-B-E'.")
        zoom = max(1.0, min(8.0, float(args.get("zoom", 3) or 3)))
        regrid_cols = max(2, min(30, int(args.get("regrid_cols", 10) or 10)))

        # Parse + validate the selection up front so we can build a canonical
        # cache key (equivalent selections reuse the same branch).
        try:
            rects = gridzoom.parse_selection(select, state.meta.ncols, state.meta.nrows)
        except ValueError as e:
            return ToolResult(text=f"zoom error: {e}")
        action_key = _normalize_action(rects, zoom, regrid_cols)

        # Cache hit: identical zoom already taken from this node -> just jump.
        cached = state.find_child(state.current_id, action_key)
        if cached is not None:
            state.redo_target[state.current_id] = cached
            state.current_id = cached
            return ToolResult(
                text=f"(cached) Re-used existing branch for {select!r}. {_pos(state)} Image shown next.",
                image=state.current,
            )

        node = state.nodes[state.current_id]
        try:
            img, new_meta, info = gridzoom.apply_gridzoom(
                state.current, state.meta, select=select,
                zoom=zoom, regrid_cols=regrid_cols,
                content_img=node.content,
            )
        except ValueError as e:
            return ToolResult(text=f"zoom error: {e}")

        rg = info["regrid"]
        parent = state.current_id
        nid = state._add_child(
            parent, img, new_meta, info["content"],
            f"zoom {select} {zoom:g}x", action_key,
        )
        state.redo_target[parent] = nid
        state.current_id = nid
        msg = (
            f"Zoomed selection {select!r} ({info['regions']} region(s)) by {zoom:g}x: "
            f"crop {info['crop_size'][0]}x{info['crop_size'][1]} -> "
            f"{info['zoomed_size'][0]}x{info['zoomed_size'][1]}. Re-gridded with "
            f"{rg['cols']} cols (A..{gridder.col_label(rg['cols'] - 1)}) x {rg['rows']} rows. "
            f"`zoom` again to go deeper, or `undo` to try a different region. {_pos(state)} "
            f"Image shown next."
        )
        return ToolResult(text=msg, image=img)

    if name == "undo":
        node = state.nodes[state.current_id]
        if node.parent is None:
            return ToolResult(text=f"Already at the root; nothing to undo. {_pos(state)}",
                              image=state.current)
        state.redo_target[node.parent] = node.id
        state.current_id = node.parent
        return ToolResult(
            text=f"Stepped back to parent '{state.nodes[state.current_id].label}'. "
                 f"{_pos(state)} Image shown next.",
            image=state.current,
        )

    if name == "redo":
        target = state.redo_target.get(state.current_id)
        if target is None or target not in state.nodes:
            return ToolResult(text=f"No forward branch to redo from here. {_pos(state)}",
                              image=state.current)
        state.current_id = target
        return ToolResult(
            text=f"Stepped forward to '{state.nodes[target].label}'. {_pos(state)} Image shown next.",
            image=state.current,
        )

    if name == "restore":
        state.current_id = state.root_id
        return ToolResult(
            text=f"Jumped back to the root '{state.nodes[state.root_id].label}' "
                 f"(the full auto-gridded map). {_pos(state)} Image shown next.",
            image=state.current,
        )

    return ToolResult(text=f"Unknown tool: {name}")
