"""Tests for zoomify.gridzoom — selection parsing + crop/zoom/regrid."""

from __future__ import annotations

import pytest

from zoomify import gridder, gridzoom


# --------------------------------------------------------------- parsing

def test_letters_to_col():
    assert gridzoom.letters_to_col("A") == 0
    assert gridzoom.letters_to_col("Z") == 25
    assert gridzoom.letters_to_col("AA") == 26
    assert gridzoom.letters_to_col("aa") == 26  # case-insensitive


def test_parse_cell_either_order():
    assert gridzoom.parse_cell("2C") == gridzoom.parse_cell("C2")
    # 2C -> row 2 (index 1), col C (index 2)
    assert gridzoom.parse_cell("2C") == (2, 1)


def test_parse_cell_bad_raises():
    with pytest.raises(ValueError):
        gridzoom.parse_cell("??")


def test_parse_region_either_order_equal():
    a = gridzoom.parse_region("1-3-B-E")
    b = gridzoom.parse_region("B-E-1-3")
    assert a == b
    # (c0, r0, c1, r1): cols B..E -> 1..4, rows 1..3 -> 0..2
    assert a == (1, 0, 4, 2)


def test_parse_region_sorts_bounds():
    assert gridzoom.parse_region("3-1-E-B") == (1, 0, 4, 2)


def test_parse_region_bad_part_count():
    with pytest.raises(ValueError):
        gridzoom.parse_region("1-3-B")


def test_parse_region_mixed_slots_rejected():
    with pytest.raises(ValueError):
        gridzoom.parse_region("1-B-3-E")


def test_parse_selection_mixed_tokens():
    rects = gridzoom.parse_selection("1-2-A-C, 4D", ncols=10, nrows=10)
    assert (0, 0, 2, 1) in rects
    assert (3, 3, 3, 3) in rects


def test_parse_selection_empty_raises():
    with pytest.raises(ValueError):
        gridzoom.parse_selection("   ", ncols=10, nrows=10)


def test_parse_selection_out_of_range_col():
    with pytest.raises(ValueError):
        gridzoom.parse_selection("1Z", ncols=3, nrows=3)


def test_parse_selection_out_of_range_row():
    with pytest.raises(ValueError):
        gridzoom.parse_selection("9A", ncols=3, nrows=3)


# --------------------------------------------------------------- apply_gridzoom

@pytest.fixture
def gridded():
    from PIL import Image
    img = Image.new("RGB", (400, 300), "white")
    return gridder.apply_grid(img, cols=8)


def test_apply_gridzoom_regrids(gridded):
    img, meta = gridded
    out, new_meta, info = gridzoom.apply_gridzoom(img, meta, "2C", zoom=3, regrid_cols=6)
    assert new_meta is not None
    assert new_meta.ncols == 6
    assert info["regions"] == 1
    assert info["zoom"] == 3
    # zoomed dims ~ crop * zoom
    cw, ch = info["crop_size"]
    zw, zh = info["zoomed_size"]
    assert zw == round(cw * 3)
    assert zh == round(ch * 3)
    assert "regrid" in info


def test_apply_gridzoom_no_regrid_returns_none_meta(gridded):
    img, meta = gridded
    out, new_meta, info = gridzoom.apply_gridzoom(img, meta, "2C", zoom=2, regrid=False)
    assert new_meta is None
    assert "regrid" not in info


def test_apply_gridzoom_zoom_must_be_positive(gridded):
    img, meta = gridded
    with pytest.raises(ValueError):
        gridzoom.apply_gridzoom(img, meta, "2C", zoom=0)


def test_apply_gridzoom_bad_selection_raises(gridded):
    img, meta = gridded
    with pytest.raises(ValueError):
        gridzoom.apply_gridzoom(img, meta, "zz", zoom=2)


def test_apply_gridzoom_keep_ruler_larger_crop(gridded):
    img, meta = gridded
    _, _, info_no = gridzoom.apply_gridzoom(img, meta, "2C", zoom=1, keep_ruler=False)
    _, _, info_keep = gridzoom.apply_gridzoom(img, meta, "2C", zoom=1, keep_ruler=True)
    cw_no, ch_no = info_no["crop_size"]
    cw_keep, ch_keep = info_keep["crop_size"]
    assert cw_keep >= cw_no and ch_keep >= ch_no
    assert (cw_keep, ch_keep) != (cw_no, ch_no)


def test_apply_gridzoom_partial_trailing_cell_crops_within_content():
    """The extra partial row/col (from rounding up) must crop to the true image
    edge — non-empty and not bleeding into the ruler margin."""
    from PIL import Image
    img, meta = gridder.apply_grid(Image.new("RGB", (400, 270), "white"), cols=8)
    assert meta.nrows == 6  # row 6 is the 20px partial strip

    # Selecting the partial last row must succeed (it is a valid labeled cell).
    out, new_meta, info = gridzoom.apply_gridzoom(img, meta, "6A", zoom=2)
    x0, y0, x1, y1 = info["px_bbox"]
    W, H = img.size
    # Crop stays inside the content region [margin, size-margin] and is non-empty.
    assert meta.margin <= x0 < x1 <= W - meta.margin
    assert meta.margin <= y0 < y1 <= H - meta.margin
    cw, ch = info["crop_size"]
    assert cw > 0 and ch > 0


def test_apply_gridzoom_content_img_avoids_baked_grid(gridded):
    """Cropping from clean content must not include the parent grid overlay."""
    from PIL import Image

    gridded_img, meta = gridded
    plain = Image.new("RGB", (400, 300), "white")

    dirty, _, _ = gridzoom.apply_gridzoom(
        gridded_img, meta, "2C", zoom=2, regrid=False,
    )
    clean, _, _ = gridzoom.apply_gridzoom(
        gridded_img, meta, "2C", zoom=2, regrid=False, content_img=plain,
    )

    def red_pixels(im):
        rgb = im.convert("RGB")
        count = 0
        for px in rgb.getdata():
            r, g, b = px
            if r > 180 and g < 80 and b < 80:
                count += 1
        return count

    assert red_pixels(dirty) > 0
    assert red_pixels(clean) == 0
