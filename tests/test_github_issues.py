"""Tests for GitHub schema inquiry issues."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from zoomify import github_issues


@pytest.fixture(autouse=True)
def _clear_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_ISSUES_REPO", raising=False)


def test_github_issues_configured(monkeypatch):
    assert github_issues.github_issues_configured() is False
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    assert github_issues.github_issues_configured() is True


def test_validate_fields():
    with pytest.raises(ValueError, match="Name"):
        github_issues._validate_name("  ")
    with pytest.raises(ValueError, match="email"):
        github_issues._validate_email("not-an-email")
    with pytest.raises(ValueError, match="use case"):
        github_issues._validate_message("")


def test_create_schema_inquiry_issue(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["method"] = req.method
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        body = json.dumps(
            {
                "number": 42,
                "html_url": "https://github.com/Zynclo-Softwares/Zoomify/issues/42",
                "title": captured["payload"]["title"],
            }
        ).encode("utf-8")
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda self: self
        resp.__exit__ = lambda *args: None
        return resp

    monkeypatch.setattr(github_issues.urllib.request, "urlopen", fake_urlopen)

    result = github_issues.create_schema_inquiry_issue(
        name="Ada Lovelace",
        email="ada@example.com",
        message="We need invoice line-item extraction.",
    )

    assert result["issue_number"] == 42
    assert captured["url"].endswith("/repos/Zynclo-Softwares/Zoomify/issues")
    assert captured["payload"]["title"] == "Schema inquiry — Ada Lovelace"
    assert "ada@example.com" in captured["payload"]["body"]
    assert captured["payload"]["labels"] == ["schema-inquiry"]


def test_create_schema_inquiry_issue_requires_token():
    with pytest.raises(RuntimeError, match="not configured"):
        github_issues.create_schema_inquiry_issue(
            name="Ada",
            email="ada@example.com",
            message="Hello",
        )
