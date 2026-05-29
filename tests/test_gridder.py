"""Tests for zoomify.gridder — grid geometry + drawing primitives."""

from __future__ import annotations

from PIL import Image

from zoomify import gridder
from zoomify.gridder import GridMeta


def test_col_label_basic():
    assert gridder.col_label(0) == "A"
    assert gridder.col_label(25) == "Z"
    assert gridder.col_label(26) == "AA"
    assert gridder.col_label(27) == "AB"
    assert gridder.col_label(51) == "AZ"
    assert gridder.col_label(52) == "BA"


def test_cell_to_px_inclusive_box():
    box = gridder.cell_to_px(10.0, 20.0, 2, 1)
    assert box == (20, 20, 30, 40)


def test_compute_geometry_exact_multiple_no_spurious_trailing_cell():
    # Regression: 207-wide image with 11 cols gives cell_w = 207/11, and
    # 207 / (207/11) is 11.000000000000002 in float, so a naive math.ceil
    # over-counts to 12 -- inventing a zero-width trailing cell that gets its
    # own duplicate label at the edge. The square image must stay 11 x 11.
    ncols, nrows, cw, ch = gridder.compute_geometry(207, 207, cols=11)
    assert ncols == 11
    assert nrows == 11

    # Same overshoot via the fixed-cell path (and a non-square case).
    ncols, nrows, _, _ = gridder.compute_geometry(230, 460, cols=7)
    assert (ncols, nrows) == (7, 14)


def test_compute_geometry_by_cols():
    ncols, nrows, cw, ch = gridder.compute_geometry(400, 300, cols=8)
    assert ncols == 8
    assert cw == 400 / 8
    assert cw == ch  # square cells
    assert nrows == round(300 / cw)


def test_compute_geometry_partial_row_adds_extra_cell():
    # 400x270 with 8 cols -> 50px square cells -> 270/50 = 5.4 rows.
    # Must round UP to 6 so the bottom 20px partial strip is still selectable.
    ncols, nrows, cw, ch = gridder.compute_geometry(400, 270, cols=8)
    assert cw == ch == 50.0
    assert nrows == 6                 # ceil(5.4), not round(5.4)==5
    assert (nrows - 1) * ch < 270     # last row starts inside the image
    assert nrows * ch >= 270          # and the grid now covers the whole height


def test_compute_geometry_by_cell_partial_cols_and_rows():
    # 410x310 with fixed 50px cells -> 8.2 cols, 6.2 rows -> ceil to 9 x 7.
    ncols, nrows, cw, ch = gridder.compute_geometry(410, 310, cell=50)
    assert cw == ch == 50.0
    assert ncols == 9
    assert nrows == 7


def test_compute_geometry_by_cell():
    ncols, nrows, cw, ch = gridder.compute_geometry(400, 300, cell=50)
    assert cw == ch == 50.0
    assert ncols == 8
    assert nrows == 6


def test_compute_geometry_defaults_to_10_cols():
    ncols, *_ = gridder.compute_geometry(1000, 500)
    assert ncols == 10


def test_apply_grid_adds_margin_and_returns_meta():
    img = Image.new("RGB", (400, 300), "white")
    gridded, meta = gridder.apply_grid(img, cols=8)
    assert isinstance(meta, GridMeta)
    assert meta.ncols == 8
    # Output is larger than the input by exactly 2*margin on each axis.
    assert gridded.size == (400 + 2 * meta.margin, 300 + 2 * meta.margin)
    assert meta.margin >= 40
    assert gridded.mode == "RGBA"


def test_grid_meta_as_dict_roundtrip():
    meta = GridMeta(ncols=8, nrows=6, cell_w=50.0, cell_h=50.0, margin=40)
    d = meta.as_dict()
    assert d == {"ncols": 8, "nrows": 6, "cell_w": 50.0, "cell_h": 50.0, "margin": 40}
