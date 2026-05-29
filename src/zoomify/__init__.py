"""Zoomify — a Gradio AI agent that extracts information from any hard-to-read
image (high-resolution, very large/long, dense, or tiny-font — maps, diagrams,
screenshots, scans, dashboards) using grid + zoom tools driven by an OpenAI
vision model."""

from . import agent, gridder, gridzoom, tools

__all__ = ["agent", "gridder", "gridzoom", "tools"]
