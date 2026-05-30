"""Tests for app.py — the Gradio handlers + trail renderer."""

from __future__ import annotations

import app
from zoomify.tools import ImageState, run_tool


# --------------------------------------------------------------- trail render

def test_render_trail_empty():
    out = app.render_trail(None)
    assert "Upload an image" in out
    assert "<style>" in out


def test_render_trail_stack_and_current_marker(small_img):
    state = ImageState.from_image(small_img, cols=6)
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    out = app.render_trail(state)
    assert out.count('class="thumb"') == 3   # root + two zoom steps
    assert "◀ current" in out
    assert "crumb current" in out
    assert 'id="zmodal"' in out
    assert "data-full=" in out


def test_render_trail_collapses_on_undo(small_img):
    state = ImageState.from_image(small_img, cols=6)
    run_tool("zoom", {"select": "2C"}, state)
    run_tool("zoom", {"select": "1A"}, state)
    run_tool("undo", {}, state)
    out = app.render_trail(state)
    assert out.count('class="thumb"') == 2


# --------------------------------------------------------------- _extract_image

def test_extract_image_from_path(tmp_path, small_img):
    p = tmp_path / "map.png"
    small_img.save(p)
    img = app._extract_image([str(p)])
    assert img is not None
    assert img.size == small_img.size


def test_extract_image_from_dict(tmp_path, small_img):
    p = tmp_path / "map.png"
    small_img.save(p)
    img = app._extract_image([{"path": str(p)}])
    assert img is not None


def test_extract_image_rejects_non_image(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("not an image")
    assert app._extract_image([str(p)]) is None


def test_extract_image_none():
    assert app._extract_image([]) is None


# --------------------------------------------------------------- reset

def test_reset_shape():
    out = app.reset()
    assert len(out) == 6
    chat, conv, state, tree, cleared, stop = out
    assert chat == []
    assert conv == []
    assert state is None
    assert "Upload an image" in tree


# --------------------------------------------------------------- respond

def _png(tmp_path, img, name="map.png"):
    p = tmp_path / name
    img.save(p)
    return str(p)


def _last(gen):
    """`respond` is a streaming generator; collect its final yielded UI tuple."""
    out = None
    for out in gen:
        pass
    return out


def test_respond_no_key(monkeypatch, tmp_path, small_img):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    msg = {"text": "read it", "files": [_png(tmp_path, small_img)]}
    chat, conv, state, tree, cleared, stop = _last(app.respond(msg, [], [], None))
    assert any("OPENAI_API_KEY" in m["content"] for m in chat)


def test_respond_rejects_non_image(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    p = tmp_path / "x.txt"
    p.write_text("nope")
    msg = {"text": "hi", "files": [str(p)]}
    chat, conv, state, tree, cleared, stop = _last(app.respond(msg, [], [], None))
    assert any("Only image files" in m["content"] for m in chat)
    assert state is None


def test_respond_first_image_turn(monkeypatch, tmp_path, small_img, scripted_client):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = scripted_client([
        ("tools", [("zoom", {"select": "2C"})]),
        ("final", "Here is the extracted info."),
    ])
    monkeypatch.setattr(app, "OpenAI", lambda *a, **k: client)

    msg = {"text": "what's here?", "files": [_png(tmp_path, small_img)]}
    chat, conv, state, tree, cleared, stop = _last(app.respond(msg, [], [], None))

    assert isinstance(state, ImageState)
    assert state.depth == 1
    assert chat[-1]["role"] == "assistant"
    assert chat[-1]["content"] == "Here is the extracted info."
    assert conv[0]["role"] == "system"
    assert "<img" in tree


def test_respond_followup_text_turn(monkeypatch, tmp_path, small_img, scripted_client):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client1 = scripted_client([("final", "first answer")])
    monkeypatch.setattr(app, "OpenAI", lambda *a, **k: client1)
    msg1 = {"text": "q1", "files": [_png(tmp_path, small_img)]}
    chat, conv, state, tree, _, _ = _last(app.respond(msg1, [], [], None))

    client2 = scripted_client([("final", "second answer")])
    monkeypatch.setattr(app, "OpenAI", lambda *a, **k: client2)
    msg2 = {"text": "q2", "files": []}
    chat, conv, state, tree, _, _ = _last(app.respond(msg2, chat, conv, state))

    assert chat[-1]["content"] == "second answer"
    assert conv[0]["role"] == "system"
    assert state.depth == 0  # follow-up resets stack to root


def test_respond_locks_input_then_unlocks(monkeypatch, tmp_path, small_img, scripted_client):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = scripted_client([
        ("tools", [("zoom", {"select": "2C"})]),
        ("final", "done"),
    ])
    monkeypatch.setattr(app, "OpenAI", lambda *a, **k: client)

    msg = {"text": "q", "files": [_png(tmp_path, small_img)]}
    updates = list(app.respond(msg, [], [], None))
    first_input, first_stop = updates[0][4], updates[0][5]
    assert first_input["interactive"] is False
    assert first_stop["interactive"] is True
    last_input, last_stop = updates[-1][4], updates[-1][5]
    assert last_input["interactive"] is True
    assert last_stop["interactive"] is False


def test_on_stop_restores_ui():
    chat, input_upd, stop_upd = app.on_stop([{"role": "user", "content": "q"}])
    assert chat[-1]["content"] == "⏹ Stopped."
    assert input_upd["interactive"] is True
    assert stop_upd["interactive"] is False


def test_respond_streams_trail_updates(monkeypatch, tmp_path, small_img, scripted_client):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = scripted_client([
        ("tools", [("zoom", {"select": "2C"})]),
        ("tools", [("zoom", {"select": "1B"})]),
        ("final", "done"),
    ])
    monkeypatch.setattr(app, "OpenAI", lambda *a, **k: client)

    msg = {"text": "q", "files": [_png(tmp_path, small_img)]}
    updates = list(app.respond(msg, [], [], None))
    assert len(updates) >= 3
    assert updates[-1][0][-1]["content"] == "done"


def test_respond_text_without_prior_image(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    msg = {"text": "hello", "files": []}
    chat, conv, state, tree, cleared, stop = _last(app.respond(msg, [], [], None))
    assert any("attach an image" in m["content"] for m in chat)


# --------------------------------------------------------------- build_ui

def test_build_ui_smoke():
    import gradio as gr
    demo = app.build_ui()
    assert isinstance(demo, gr.Blocks)
