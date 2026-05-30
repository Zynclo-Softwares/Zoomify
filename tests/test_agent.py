"""Tests for zoomify.agent — the OpenAI tool-calling loop."""

from __future__ import annotations

from PIL import Image

from zoomify.agent import (
    MAX_TOOL_ITERATIONS,
    build_user_turn,
    _prune_old_images,
    run_agent,
)
from zoomify.tools import ImageState


def _img():
    return Image.new("RGB", (200, 150), "white")


# --------------------------------------------------------------- helpers


def test_build_user_turn_text_only():
    turn = build_user_turn("hello", None)
    assert turn["role"] == "user"
    parts = turn["content"]
    assert parts[0] == {"type": "text", "text": "hello"}
    assert all(p["type"] != "image_url" for p in parts)


def test_build_user_turn_with_image():
    turn = build_user_turn("hello", _img())
    types = [p["type"] for p in turn["content"]]
    assert "text" in types and "image_url" in types


def test_prune_old_images_keeps_recent():
    msgs = []
    for i in range(6):
        msgs.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"msg{i}"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}},
                ],
            }
        )
    _prune_old_images(msgs, keep=2)
    image_msgs = [
        m
        for m in msgs
        if isinstance(m.get("content"), list)
        and any(p.get("type") == "image_url" for p in m["content"])
    ]
    assert len(image_msgs) == 2
    # older ones became text placeholders
    assert isinstance(msgs[0]["content"], str)
    assert "omitted" in msgs[0]["content"]
    assert "msg0" in msgs[0]["content"]


# --------------------------------------------------------------- run_agent


def test_run_agent_returns_final_without_tools(scripted_client):
    client = scripted_client([("final", "the answer")])
    state = ImageState.from_image(_img(), cols=6)
    msgs = [{"role": "system", "content": "sys"}, build_user_turn("q", state.current)]
    final, produced, out = run_agent(msgs, state, client=client)
    assert final == "the answer"
    assert produced == []
    # parallel_tool_calls disabled (stateful tools)
    assert client.calls[0]["parallel_tool_calls"] is False


def test_run_agent_executes_tool_then_answers(scripted_client):
    client = scripted_client(
        [
            ("tools", [("zoom", {"select": "2C"})]),
            ("final", "done reading"),
        ]
    )
    state = ImageState.from_image(_img(), cols=6)
    msgs = [{"role": "system", "content": "sys"}, build_user_turn("q", state.current)]
    final, produced, out = run_agent(msgs, state, client=client)
    assert final == "done reading"
    assert len(produced) == 1
    assert state.depth == 1
    # role ordering: ... assistant(tool_call), tool, user(image), assistant(final)
    roles = [m["role"] for m in out]
    assert roles[0] == "system"
    assert "tool" in roles
    # a follow-up user message carries the produced image
    assert any(
        m["role"] == "user"
        and isinstance(m["content"], list)
        and any(p.get("type") == "image_url" for p in m["content"])
        for m in out[2:]
    )


def test_run_agent_max_iterations_fallback(looping_client):
    client = looping_client(name="undo")  # never finishes
    state = ImageState.from_image(_img(), cols=6)
    msgs = [{"role": "system", "content": "sys"}, build_user_turn("q", state.current)]
    final, produced, out = run_agent(msgs, state, client=client)
    assert "tool-call limit" in final
    assert len(client.calls) == MAX_TOOL_ITERATIONS


def test_run_agent_handles_bad_tool_arguments(scripted_client):
    # zoom with a bad selection -> tool returns an error string, loop continues
    client = scripted_client(
        [
            ("tools", [("zoom", {"select": "zz"})]),
            ("final", "couldn't read"),
        ]
    )
    state = ImageState.from_image(_img(), cols=6)
    msgs = [{"role": "system", "content": "sys"}, build_user_turn("q", state.current)]
    final, produced, out = run_agent(msgs, state, client=client)
    assert final == "couldn't read"
    assert len(state.path) == 0  # bad selection pushed nothing
    tool_msgs = [m for m in out if m["role"] == "tool"]
    assert any("zoom error" in m["content"] for m in tool_msgs)


def test_iter_agent_yields_state_per_tool_round(scripted_client):
    from zoomify.agent import iter_agent

    client = scripted_client(
        [
            ("tools", [("zoom", {"select": "2C"})]),
            ("tools", [("zoom", {"select": "1B"})]),
            ("final", "done"),
        ]
    )
    state = ImageState.from_image(_img(), cols=6)
    msgs = [{"role": "system", "content": "sys"}, build_user_turn("q", state.current)]

    gen = iter_agent(msgs, state, client=client)
    snapshots = []
    try:
        while True:
            snapshots.append(next(gen))
    except StopIteration as stop:
        final, produced, out = stop.value

    # one yield per tool round (two zooms), each handing back the live state
    assert len(snapshots) == 2
    assert all(s is state for s in snapshots)
    assert final == "done"
    assert len(produced) == 2


def test_keep_recent_image_msgs_is_one():
    """Only the current image should remain in context; the model must navigate
    (undo/redo/restore) to revisit earlier checkpoints."""
    from zoomify.agent import KEEP_RECENT_IMAGE_MSGS

    assert KEEP_RECENT_IMAGE_MSGS == 1
