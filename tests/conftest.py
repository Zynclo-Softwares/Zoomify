"""Shared fixtures for the Zoomify test suite."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def small_img() -> Image.Image:
    """A small synthetic 'map' image so tests stay fast."""
    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 180, 140], outline="black", width=2)
    d.rectangle([220, 160, 380, 280], fill=(200, 220, 255))
    d.text((30, 30), "PANEL A", fill="black")
    d.text((230, 170), "INVERTER", fill="black")
    return img


@pytest.fixture
def state(small_img):
    from zoomify.tools import ImageState
    return ImageState.from_image(small_img, cols=8)


# --------------------------------------------------------------- fake OpenAI

def _tool_call(call_id: str, name: str, args: dict):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


class ScriptedClient:
    """A fake OpenAI client driven by a script of steps.

    Each step is one of:
      ("tools", [(name, args), ...])  -> assistant requests tool call(s)
      ("final", "text")               -> assistant final content
    Steps beyond the script return a final "done" message.
    """

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        idx = len(self.calls) - 1
        step = self.steps[idx] if idx < len(self.steps) else ("final", "done")
        if step[0] == "tools":
            tcs = [_tool_call(f"c{idx}_{i}", nm, ar)
                   for i, (nm, ar) in enumerate(step[1])]
            msg = SimpleNamespace(content=None, tool_calls=tcs)
        else:
            msg = SimpleNamespace(content=step[1], tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class LoopingToolClient:
    """A fake client that ALWAYS requests the same tool call (to exercise the
    max-iteration guard)."""

    def __init__(self, name="undo", args=None):
        self.name = name
        self.args = args or {}
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        tc = _tool_call(f"c{len(self.calls)}", self.name, self.args)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tc]))]
        )


@pytest.fixture
def scripted_client():
    return ScriptedClient


@pytest.fixture
def looping_client():
    return LoopingToolClient
