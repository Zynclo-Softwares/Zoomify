"""
gridder.py — TOOL 1.

Overlay a labeled chessboard ruling system on an image. The result has a thin
red grid plus a margin border printing column letters (A, B, ...) along top +
bottom and row numbers (1, 2, ...) along left + right. Those labels let the AI
(or a human) reference any cell as "2C" / "C2", a rectangular region as
"1-3-B-E", a discrete list as "1C,3B,4C", etc.

This module also holds the shared grid-drawing primitives used by gridzoom.py
(``col_label``, ``cell_to_px``, ``draw_grid``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None  # allow very large / high-resolution images

DEFAULT_TARGET_CELL_PX = 120
MIN_GRID_COLS = 3
MAX_GRID_COLS = 24


def auto_grid_cols(width: int, height: int, *,
                   target_cell: float = DEFAULT_TARGET_CELL_PX,
                   min_cols: int = MIN_GRID_COLS,
                   max_cols: int = MAX_GRID_COLS,
                   parent_cell_w: float | None = None) -> int:
    """Pick a column count so cells stay readable on ``width`` x ``height``.

    When ``parent_cell_w`` is given (during re-grid after zoom), keep a similar
    cell size to the view being zoomed from; otherwise target ~``target_cell``
    pixels per cell on the shorter side.
    """
    width = max(1, width)
    height = max(1, height)
    if parent_cell_w and parent_cell_w > 0:
        cols = round(width / parent_cell_w)
    else:
        cols = round(min(width, height) / target_cell)
    return max(min_cols, min(max_cols, cols or min_cols))


@dataclass
class GridMeta:
    """Geometry of a grid that has been overlaid on an image.

    ``margin`` is the ruler thickness added on every side by :func:`draw_grid`.
    ``cell_w`` / ``cell_h`` are measured in the *inner content* pixel space
    (i.e. excluding the margin). gridzoom uses this to translate a cell
    selection into a pixel crop box.
    """

    ncols: int
    nrows: int
    cell_w: float
    cell_h: float
    margin: int

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------- helpers

def col_label(i: int) -> str:
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA', ..."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def cell_to_px(cell_w: float, cell_h: float, c: int, r: int) -> tuple[int, int, int, int]:
    """Inclusive cell (col c, row r) -> pixel box (x0, y0, x1, y1) in inner space.

    Uses floor for the start edges and ceil for the end edges so that even a
    thin *partial* trailing cell (created when the image size isn't an exact
    multiple of the cell size) always maps to a non-empty pixel span.
    """
    return (
        int(math.floor(c * cell_w)),
        int(math.floor(r * cell_h)),
        int(math.ceil((c + 1) * cell_w)),
        int(math.ceil((r + 1) * cell_h)),
    )


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# --------------------------------------------------------------- geometry

def _cells_needed(extent: float, cell: float) -> int:
    """Number of cells of size ``cell`` needed to cover ``extent`` pixels.

    Rounds **up** so a leftover partial strip still gets its own trailing
    cell. A small tolerance snaps near-integer ratios down first: floating
    point makes an exact multiple like ``207 / (207 / 11)`` evaluate to
    ``11.000000000000002``, and a naive ``ceil`` would bump that to ``12`` —
    inventing a spurious zero-width trailing cell that then receives its own
    (duplicate-looking) label. Guarding with an epsilon avoids that.
    """
    units = extent / cell
    nearest = round(units)
    if abs(units - nearest) < 1e-9:
        units = nearest
    return max(1, math.ceil(units))


def compute_geometry(width: int, height: int, cols: int | None = None,
                     cell: int | None = None) -> tuple[int, int, float, float]:
    """Return (ncols, nrows, cell_w, cell_h) for an image of the given size.

    Provide either ``cols`` (number of columns; rows derived to keep cells
    square) or ``cell`` (fixed square cell size in pixels). When ``cols`` is
    omitted, :func:`auto_grid_cols` picks a readable column count from size.

    Derived counts round **up** (ceil): when the image size isn't an exact
    multiple of the cell size, the leftover strip gets its own (partial)
    trailing cell so that every pixel of the image is referenceable by a
    labeled cell, instead of being orphaned below/right of the last full cell.
    """
    if cell:
        cell_w = cell_h = float(cell)
        ncols = _cells_needed(width, cell_w)
        nrows = _cells_needed(height, cell_h)
    else:
        ncols = max(1, cols if cols is not None else auto_grid_cols(width, height))
        cell_w = width / ncols
        cell_h = cell_w  # square cells
        nrows = _cells_needed(height, cell_h)
    return ncols, nrows, cell_w, cell_h


# --------------------------------------------------------------- drawing

def draw_grid(img: Image.Image, ncols: int, nrows: int,
              cell_w: float, cell_h: float) -> tuple[Image.Image, GridMeta]:
    """Overlay a labeled grid + ruler margin on ``img``.

    Returns the composited RGBA image and the :class:`GridMeta` describing it.
    """
    src = img.convert("RGBA")
    W, H = src.size

    # Margin sized to the cell so labels stay roomy and readable.
    margin = max(40, int(min(cell_w, cell_h) * 0.45))
    font_size = max(18, int(margin * 0.55))
    font = load_font(font_size)

    canvas = Image.new("RGBA", (W + 2 * margin, H + 2 * margin), (245, 245, 245, 255))
    canvas.paste(src, (margin, margin))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    line_color = (220, 30, 30, 230)
    line_w = max(2, int(min(cell_w, cell_h) / 70))

    for c in range(ncols + 1):
        x = margin + min(int(round(c * cell_w)), W)  # clamp trailing partial line to edge
        draw.line([(x, margin), (x, margin + H)], fill=line_color, width=line_w)
    for r in range(nrows + 1):
        y = margin + min(int(round(r * cell_h)), H)
        draw.line([(margin, y), (margin + W, y)], fill=line_color, width=line_w)

    border_w = max(3, line_w + 1)
    draw.rectangle([margin, margin, margin + W, margin + H],
                   outline=line_color, width=border_w)

    label_fill = (0, 0, 0, 255)

    # Column letters along top AND bottom margins. Centre each label on the
    # cell's *clamped* span so a thin partial trailing cell's label stays over
    # the image rather than drifting into the ruler margin.
    for c in range(ncols):
        x0 = min(int(round(c * cell_w)), W)
        x1 = min(int(round((c + 1) * cell_w)), W)
        cx = margin + (x0 + x1) // 2
        label = col_label(c)
        bb = draw.textbbox((0, 0), label, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((cx - tw // 2 - bb[0], margin // 2 - th // 2 - bb[1]),
                  label, fill=label_fill, font=font)
        draw.text((cx - tw // 2 - bb[0], margin + H + margin // 2 - th // 2 - bb[1]),
                  label, fill=label_fill, font=font)

    # Row numbers along left AND right margins.
    for r in range(nrows):
        y0 = min(int(round(r * cell_h)), H)
        y1 = min(int(round((r + 1) * cell_h)), H)
        cy = margin + (y0 + y1) // 2
        label = str(r + 1)
        bb = draw.textbbox((0, 0), label, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((margin // 2 - tw // 2 - bb[0], cy - th // 2 - bb[1]),
                  label, fill=label_fill, font=font)
        draw.text((margin + W + margin // 2 - tw // 2 - bb[0], cy - th // 2 - bb[1]),
                  label, fill=label_fill, font=font)

    composited = Image.alpha_composite(canvas, overlay)
    meta = GridMeta(ncols=ncols, nrows=nrows, cell_w=cell_w, cell_h=cell_h, margin=margin)
    return composited, meta


# --------------------------------------------------------------- tool entry

def apply_grid(img: Image.Image, cols: int | None = None,
               cell: int | None = None) -> tuple[Image.Image, GridMeta]:
    """Tool entry point: grid a plain image, returning (gridded_image, meta).

    When ``cols`` and ``cell`` are both omitted, column count is chosen from
    image size via :func:`auto_grid_cols`.
    """
    W, H = img.size
    ncols, nrows, cell_w, cell_h = compute_geometry(W, H, cols=cols, cell=cell)
    return draw_grid(img, ncols, nrows, cell_w, cell_h)
