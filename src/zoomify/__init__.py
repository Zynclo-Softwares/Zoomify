"""Zoomify — grid + zoom vision tools for AI agents, served as a remote MCP
server. Lets any agent read hard-to-read images (high-resolution, very
large/long, dense, or tiny-font — drawings, maps, scans, screenshots, PDFs)."""

from .core import gridder, gridzoom, tools

__all__ = ["gridder", "gridzoom", "tools"]
