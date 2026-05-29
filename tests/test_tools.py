"""Tests for zoomify.tools — the branching, cached image DAG + tool dispatch."""

from __future__ import annotations

from zoomify.tools import ImageState, encode_image, run_tool


# --------------------------------------------------------------- state setup

def test_from_image_auto_grids_root(state):
    assert state.root_id == 0
    assert state.current_id == 0
    assert len(state.nodes) == 1
    root = state.nodes[0]
    assert root.parent is None
    assert root.meta.ncols == 8
    assert root.label.startswith("grid")


def test_current_and_meta_properties(state):
    assert state.current is state.nodes[0].image
    assert state.meta is state.nodes[0].meta


# --------------------------------------------------------------- zoom / branch

def test_zoom_creates_branch(state):
    res = run_tool("zoom", {"select": "2C"}, state)
    assert res.image is not None
    assert "Zoomed" in res.text
    assert len(state.nodes) == 2
    assert state.current_id == 1
    assert state.depth(1) == 1
    assert state.nodes[1].parent == 0


def test_zoom_stores_clean_content(state):
    run_tool("zoom", {"select": "2C"}, state)
    child = state.nodes[state.current_id]
    assert child.content is not state.original
    assert child.content.mode in ("RGB", "RGBA")
    assert child.image.size != child.content.size  # gridded image has ruler margin


def test_zoom_then_deeper(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    assert state.depth(state.current_id) == 2
    assert len(state.nodes) == 3


def test_zoom_bad_selection_no_node_added(state):
    res = run_tool("zoom", {"select": "zz"}, state)
    assert res.text.startswith("zoom error")
    assert len(state.nodes) == 1
    assert state.current_id == 0


def test_zoom_missing_select(state):
    res = run_tool("zoom", {}, state)
    assert "Missing" in res.text
    assert len(state.nodes) == 1


# --------------------------------------------------------------- caching

def test_cache_hit_same_selection(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("undo", {}, state)
    res = run_tool("zoom", {"select": "2C"}, state)
    assert "cached" in res.text
    assert len(state.nodes) == 2  # no new node created


def test_cache_hit_canonical_region_equivalent(state):
    run_tool("zoom", {"select": "1-2-A-C"}, state)
    run_tool("undo", {}, state)
    res = run_tool("zoom", {"select": "A-C-1-2"}, state)
    assert "cached" in res.text
    assert len(state.nodes) == 2


def test_cache_hit_canonical_cell_equivalent(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("undo", {}, state)
    res = run_tool("zoom", {"select": "C2"}, state)
    assert "cached" in res.text
    assert len(state.nodes) == 2


def test_different_zoom_factor_is_distinct_branch(state):
    run_tool("zoom", {"select": "2C", "zoom": 3}, state)
    run_tool("undo", {}, state)
    run_tool("zoom", {"select": "2C", "zoom": 4}, state)
    assert len(state.nodes) == 3  # distinct action keys


# --------------------------------------------------------------- navigation

def test_undo_redo(state):
    run_tool("zoom", {"select": "2C"}, state)
    assert state.current_id == 1
    run_tool("undo", {}, state)
    assert state.current_id == 0
    run_tool("redo", {}, state)
    assert state.current_id == 1


def test_undo_at_root_is_noop(state):
    res = run_tool("undo", {}, state)
    assert "root" in res.text.lower()
    assert state.current_id == 0


def test_redo_with_no_target(state):
    res = run_tool("redo", {}, state)
    assert "No forward" in res.text
    assert state.current_id == 0


def test_restore_jumps_to_root(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    res = run_tool("restore", {}, state)
    assert state.current_id == state.root_id
    assert "root" in res.text.lower()


def test_reset_to_root_moves_pointer_without_losing_branches(state):
    # Drill two levels deep, then reset (as a new query does).
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    assert state.current_id != state.root_id
    n_nodes = len(state.nodes)

    state.reset_to_root()
    assert state.current_id == state.root_id      # pointer back at the top
    assert len(state.nodes) == n_nodes            # branches kept (cache intact)

    # Re-zooming the same region is still a cache hit, not a new node.
    res = run_tool("zoom", {"select": "2C"}, state)
    assert "cached" in res.text
    assert len(state.nodes) == n_nodes


def test_undo_then_different_zoom_makes_new_branch(state):
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("undo", {}, state)
    run_tool("zoom", {"select": "3D"}, state)
    # root has two children now
    assert len(state.nodes[0].children) == 2


def test_unknown_tool(state):
    res = run_tool("frobnicate", {}, state)
    assert "Unknown tool" in res.text


# --------------------------------------------------------------- clamps

def test_zoom_factor_clamped(state):
    res = run_tool("zoom", {"select": "2C", "zoom": 99}, state)
    assert "8x" in res.text  # clamped to 8


def test_regrid_cols_clamped_low(state):
    run_tool("zoom", {"select": "2C", "regrid_cols": 1}, state)
    assert state.nodes[state.current_id].meta.ncols == 2  # clamped up to 2


def test_regrid_cols_clamped_high(state):
    run_tool("zoom", {"select": "2C", "regrid_cols": 999}, state)
    assert state.nodes[state.current_id].meta.ncols == 30  # clamped to 30


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


# --------------------------------------------------------------- find_child

def test_find_child(state):
    run_tool("zoom", {"select": "2C"}, state)
    key = state.nodes[1].action_key
    assert state.find_child(0, key) == 1
    assert state.find_child(0, "nope") is None
