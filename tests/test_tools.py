"""Tests for zoomify.tools — stack-based zoom path + tool dispatch."""

from __future__ import annotations

from zoomify.tools import ImageState, ZoomStep, encode_image, run_tool


# --------------------------------------------------------------- state setup

def test_from_image_auto_grids_root(state):
    assert state.depth == 0
    assert state.path == []
    assert state.root_meta.ncols == 8
    assert state.root_label.startswith("grid")


def test_current_and_meta_properties(state):
    assert state.current is state.root_image
    assert state.meta is state.root_meta


# --------------------------------------------------------------- zoom / stack

def test_zoom_pushes_step(state):
    res = run_tool("zoom", {"select": "2C"}, state)
    assert res.image is not None
    assert "Pushed" in res.text
    assert len(state.path) == 1
    assert state.depth == 1
    assert state.path[0].select == "2C"


def test_zoom_renders_clean_content(state):
    run_tool("zoom", {"select": "2C"}, state)
    assert state.content.size[0] > 0
    assert state.current.size != state.content.size  # gridded has ruler margin


def test_zoom_then_deeper(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    assert state.depth == 2
    assert len(state.path) == 2


def test_zoom_bad_selection_does_not_push(state):
    res = run_tool("zoom", {"select": "zz"}, state)
    assert res.text.startswith("zoom error")
    assert len(state.path) == 0


def test_zoom_missing_select(state):
    res = run_tool("zoom", {}, state)
    assert "Missing" in res.text
    assert len(state.path) == 0


def test_undo_then_same_zoom_recomputes(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("undo", {}, state)
    assert len(state.path) == 0
    res = run_tool("zoom", {"select": "2C"}, state)
    assert "Pushed" in res.text
    assert len(state.path) == 1


def test_undo_then_different_zoom_replaces_tail(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("undo", {}, state)
    run_tool("zoom", {"select": "3D"}, state)
    assert len(state.path) == 1
    assert state.path[0].select == "3D"


# --------------------------------------------------------------- navigation

def test_undo_redo(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("undo", {}, state)
    assert state.depth == 0
    run_tool("redo", {}, state)
    assert state.depth == 1
    assert state.path[0].select == "2C"


def test_undo_at_root_is_noop(state):
    res = run_tool("undo", {}, state)
    assert "root" in res.text.lower()
    assert state.depth == 0


def test_redo_with_no_target(state):
    res = run_tool("redo", {}, state)
    assert "No zoom step" in res.text
    assert state.depth == 0


def test_restore_clears_stack(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    res = run_tool("restore", {}, state)
    assert state.depth == 0
    assert "root" in res.text.lower()


def test_reset_to_root_clears_path(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    state.reset_to_root()
    assert state.depth == 0
    assert state.path == []


def test_checkpoint_labels(state):
    run_tool("zoom", {"select": "2C", "zoom": 3}, state)
    labels = state.checkpoint_labels()
    assert labels[0].startswith("grid")
    assert "2C" in labels[1]


def test_render_prefix_depths(state):
    run_tool("zoom", {"select": "2C"}, state)
    root_view = state.render_prefix(0)
    deep_view = state.render_prefix(1)
    assert root_view.size != deep_view.size


def test_unknown_tool(state):
    res = run_tool("frobnicate", {}, state)
    assert "Unknown tool" in res.text


# --------------------------------------------------------------- clamps

def test_zoom_factor_clamped(state):
    res = run_tool("zoom", {"select": "2C", "zoom": 99}, state)
    assert state.path[-1].zoom == 8.0
    assert "8x" not in res.text or "8" in res.text


def test_regrid_cols_clamped_low(state):
    run_tool("zoom", {"select": "2C", "regrid_cols": 1}, state)
    assert state.path[-1].regrid_cols == 2


def test_regrid_cols_clamped_high(state):
    run_tool("zoom", {"select": "2C", "regrid_cols": 999}, state)
    assert state.path[-1].regrid_cols == 30
    assert state.meta.ncols == 30


# --------------------------------------------------------------- encoding

def test_encode_image_data_uri(small_img):
    uri = encode_image(small_img, max_side=200, fmt="PNG")
    assert uri.startswith("data:image/png;base64,")


def test_encode_image_jpeg_mime(small_img):
    uri = encode_image(small_img, max_side=64, fmt="JPEG")
    assert uri.startswith("data:image/jpeg;base64,")


def test_encode_image_downscales(small_img):
    import base64
    import io

    from PIL import Image

    uri = encode_image(small_img, max_side=100, fmt="PNG")
    raw = base64.b64decode(uri.split(",", 1)[1])
    decoded = Image.open(io.BytesIO(raw))
    assert max(decoded.size) <= 100


def test_zoom_step_label():
    step = ZoomStep(select="2C", zoom=2.5, regrid_cols=10)
    assert step.label == "zoom 2C 2.5x"
