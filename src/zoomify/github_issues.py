"""Create GitHub issues for inbound schema-service inquiries."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_REPO = "Zynclo-Softwares/Zoomify"
DEFAULT_LABEL = "schema-inquiry"

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def github_issues_repo() -> str:
    return os.environ.get("GITHUB_ISSUES_REPO", DEFAULT_REPO).strip() or DEFAULT_REPO


def github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    return token or None


def github_issues_configured() -> bool:
    return bool(github_token())


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Name is required")
    if len(cleaned) > 120:
        raise ValueError("Name is too long")
    return cleaned


def _validate_email(email: str) -> str:
    cleaned = email.strip()
    if not cleaned:
        raise ValueError("Email is required")
    if len(cleaned) > 254 or not _EMAIL_RE.match(cleaned):
        raise ValueError("Enter a valid email address")
    return cleaned


def _validate_message(message: str) -> str:
    cleaned = message.strip()
    if not cleaned:
        raise ValueError("Tell us about your documents or use case")
    if len(cleaned) > 8000:
        raise ValueError("Message is too long")
    return cleaned


def create_schema_inquiry_issue(*, name: str, email: str, message: str) -> dict:
    """Open a GitHub issue in the configured repo. Returns issue metadata."""
    token = github_token()
    if not token:
        raise RuntimeError("Schema inquiry is not configured on this server")

    safe_name = _validate_name(name)
    safe_email = _validate_email(email)
    safe_message = _validate_message(message)

    repo = github_issues_repo()
    title = f"Schema inquiry — {safe_name}"
    body = (
        f"**Name:** {safe_name}\n"
        f"**Email:** {safe_email}\n\n"
        f"**Message:**\n\n{safe_message}\n\n"
        "---\n"
        "_Submitted via the Zoomify schema inquiry form._"
    )

    payload = {
        "title": title[:256],
        "body": body,
        "labels": [DEFAULT_LABEL],
    }

    url = f"https://api.github.com/repos/{repo}/issues"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "Zoomify-Schema-Inquiry",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach GitHub to create the issue") from exc

    return {
        "issue_number": data.get("number"),
        "issue_url": data.get("html_url"),
        "title": data.get("title"),
    }
