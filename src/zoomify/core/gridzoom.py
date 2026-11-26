"""
gridzoom.py — TOOL 2.

Given an image already gridded by gridder.py (its :class:`GridMeta`) and a cell
selection, crop the union bounding box of that selection, upscale it by ``zoom``,
and re-overlay a fresh grid on the zoomed crop so the AI can keep drilling in.

Selection grammar (case-insensitive):

  Single cell:           2C        (row 2, col C)   — letters/digits in any order
                         C2
  Discrete cells:        1C,3B,4C
  Rectangular region:    1-3-B-E   (rows 1..3, cols B..E)
  Multiple regions:      1-2-A-F, 3-5-G-J
  Mixed:                 1-2-A-F, 4C, 5G

The crop = union bounding box of all listed cells / regions.
"""

from __future__ import annotations

import math
import re

from PIL import Image

from . import gridder
from .gridder import GridMeta

Image.MAX_IMAGE_PIXELS = None


# --------------------------------------------------------------- selection


def letters_to_col(s: str) -> int:
    s = s.upper()
    col = 0
    for c in s:
        if not ("A" <= c <= "Z"):
            raise ValueError(f"bad letters {s!r}")
        col = col * 26 + (ord(c) - ord("A") + 1)
    return col - 1


def parse_cell(tok: str) -> tuple[int, int]:
    """Accept '2C' or 'C2' -> (col, row), zero-based."""
    t = tok.strip().upper()
    m = re.fullmatch(r"(\d+)([A-Z]+)", t)
    if m:
        return letters_to_col(m.group(2)), int(m.group(1)) - 1
    m = re.fullmatch(r"([A-Z]+)(\d+)", t)
    if m:
        return letters_to_col(m.group(1)), int(m.group(2)) - 1
    raise ValueError(f"bad cell {tok!r}")


def parse_region(tok: str) -> tuple[int, int, int, int]:
    """'R1-R2-C1-C2' -> (c0, r0, c1, r1) inclusive cell-rect.

    Letters and digits can be in either slot pair: '1-3-B-E' and 'B-E-1-3'
    both work.
    """
    parts = [p.strip().upper() for p in tok.split("-") if p.strip()]
    if len(parts) != 4:
        raise ValueError(f"bad region {tok!r} (expected 4 dash-separated parts)")
    is_digit = [p.isdigit() for p in parts]
    is_alpha = [p.isalpha() for p in parts]
    if all(is_digit[:2]) and all(is_alpha[2:]):
        r1, r2, c1, c2 = parts
    elif all(is_alpha[:2]) and all(is_digit[2:]):
        c1, c2, r1, r2 = parts
    else:
        raise ValueError(f"bad region {tok!r} (mix of letters/digits not understood)")
    ra, rb = int(r1) - 1, int(r2) - 1
    ca, cb = letters_to_col(c1), letters_to_col(c2)
    c0, c1_ = sorted((ca, cb))
    r0, r1_ = sorted((ra, rb))
    return c0, r0, c1_, r1_


def parse_selection(s: str, ncols: int, nrows: int) -> list[tuple[int, int, int, int]]:
    """Return list of (c0, r0, c1, r1) inclusive cell-rects."""
    rects: list[tuple[int, int, int, int]] = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.count("-") >= 1 and not re.fullmatch(r"[A-Za-z0-9]+", tok):
            rects.append(parse_region(tok))
        else:
            c, r = parse_cell(tok)
            rects.append((c, r, c, r))

    if not rects:
        raise ValueError("empty selection")

    for c0, r0, c1, r1 in rects:
        for c in (c0, c1):
            if not (0 <= c < ncols):
                raise ValueError(
                    f"column out of range: {gridder.col_label(c)} "
                    f"(have A..{gridder.col_label(ncols - 1)})"
                )
        for r in (r0, r1):
            if not (0 <= r < nrows):
                raise ValueError(f"row out of range: {r + 1} (have 1..{nrows})")
    return rects


# --------------------------------------------------------------- tool entry


def selection_bbox(
    meta: GridMeta, select: str, content_w: int, content_h: int
) -> tuple[tuple[int, int, int, int], list]:
    """Map a cell selection to a pixel bbox in inner-content coordinates."""
    rects = parse_selection(select, meta.ncols, meta.nrows)
    pix = []
    for c0, r0, c1, r1 in rects:
        x0, y0, _, _ = gridder.cell_to_px(meta.cell_w, meta.cell_h, c0, r0)
        _, _, x1, y1 = gridder.cell_to_px(meta.cell_w, meta.cell_h, c1, r1)
        pix.append((x0, y0, x1, y1))

    x0 = min(p[0] for p in pix)
    y0 = min(p[1] for p in pix)
    x1 = max(p[2] for p in pix)
    y1 = max(p[3] for p in pix)

    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(content_w, x1)
    y1 = min(content_h, y1)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("selection produced an empty crop after clipping")
    return (x0, y0, x1, y1), rects


def apply_gridzoom(
    img: Image.Image,
    meta: GridMeta,
    select: str,
    zoom: float = 3.0,
    regrid_cols: int = 10,
    regrid: bool = True,
    keep_ruler: bool = False,
    content_img: Image.Image | None = None,
) -> tuple[Image.Image, GridMeta, dict]:
    """Crop the selection, upscale, and re-grid.

    ``meta`` describes the grid on ``img``. When ``content_img`` is given it
    must be the ungridded inner content (same pixel size as the gridded image
    minus its ruler margin); the crop is taken from that clean image so old
    grid lines are not baked into zoomed results. Returns
    (result_image, new_meta, info). ``new_meta`` describes the re-applied grid
    on the zoomed crop (or ``None`` if ``regrid`` is False).
    """
    if zoom <= 0:
        raise ValueError("zoom must be > 0")

    margin = meta.margin
    W, H = img.size

    if content_img is not None:
        cw_img, ch_img = content_img.size
        inner_w = W - 2 * margin
        inner_h = H - 2 * margin
        if (cw_img, ch_img) != (inner_w, inner_h):
            raise ValueError(
                f"content_img size {cw_img}x{ch_img} does not match inner "
                f"content {inner_w}x{inner_h}"
            )
        bbox, rects = selection_bbox(meta, select, cw_img, ch_img)
        crop = content_img.crop(bbox)
    else:
        rects = parse_selection(select, meta.ncols, meta.nrows)
        pix = []
        for c0, r0, c1, r1 in rects:
            x0, y0, _, _ = gridder.cell_to_px(meta.cell_w, meta.cell_h, c0, r0)
            _, _, x1, y1 = gridder.cell_to_px(meta.cell_w, meta.cell_h, c1, r1)
            pix.append((x0 + margin, y0 + margin, x1 + margin, y1 + margin))

        x0 = min(p[0] for p in pix)
        y0 = min(p[1] for p in pix)
        x1 = max(p[2] for p in pix)
        y1 = max(p[3] for p in pix)

        if margin > 0 and keep_ruler:
            x0 -= margin
            y0 -= margin
            x1 += margin
            y1 += margin
            lo_x = lo_y = 0
            hi_x, hi_y = W, H
        else:
            lo_x = lo_y = margin
            hi_x, hi_y = W - margin, H - margin

        x0 = max(lo_x, x0)
        y0 = max(lo_y, y0)
        x1 = min(hi_x, x1)
        y1 = min(hi_y, y1)
        if x1 <= x0 or y1 <= y0:
            raise ValueError("selection produced an empty crop after clipping")
        bbox = (x0, y0, x1, y1)
        crop = img.crop(bbox)
    cw, ch = crop.size
    nw, nh = max(1, int(round(cw * zoom))), max(1, int(round(ch * zoom)))
    zoomed = crop.resize((nw, nh), Image.LANCZOS)

    info = {
        "selection": select,
        "regions": len(rects),
        "px_bbox": bbox,
        "crop_size": (cw, ch),
        "zoomed_size": (nw, nh),
        "zoom": zoom,
        "content": zoomed,
    }

    if not regrid:
        return zoomed, None, info

    rcols = max(1, regrid_cols)
    rcell = nw / rcols
    rrows = max(1, math.ceil(nh / rcell))
    result, new_meta = gridder.draw_grid(zoomed, rcols, rrows, rcell, rcell)
    info["regrid"] = {"cols": rcols, "rows": rrows, "cell": rcell}
    return result, new_meta, info


def render_at_path(
    original: Image.Image, root_meta: GridMeta, root_gridded: Image.Image, steps
) -> tuple[Image.Image, GridMeta, Image.Image]:
    """Replay a zoom recipe from the root and return (gridded, meta, content).

    ``steps`` is an iterable of objects with ``select``, ``zoom``, and
    ``regrid_cols`` attributes. An empty path returns the root view.
    """
    if not steps:
        return root_gridded, root_meta, original.convert("RGB")

    content = original.convert("RGB")
    meta = root_meta
    gridded = root_gridded
    for step in steps:
        gridded, meta, info = apply_gridzoom(
            gridded,
            meta,
            step.select,
            step.zoom,
            step.regrid_cols,
            content_img=content,
        )
        content = info["content"]
    return gridded, meta, content
