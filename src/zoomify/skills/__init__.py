"""Agent skills — short playbooks that teach an agent to use the zoom tools well.

Each skill is a Markdown file in ``src/zoomify/skills/`` with a small
frontmatter block::

    ---
    name: engineering-drawings
    title: Engineering drawings & single-line diagrams
    description: One line on when an agent should read this skill.
    ---

    ...markdown body...

Drop a new ``.md`` file in that folder and it is served automatically as an MCP
resource (``zoomify://skills/<name>``), an MCP prompt, through the
``read_skill`` tool, and on the web setup page (``GET /api/skills``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
CORE_SKILL = "zoom-basics"

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


@dataclass(frozen=True)
class Skill:
    name: str
    title: str
    description: str
    body: str

    @property
    def uri(self) -> str:
        return f"zoomify://skills/{self.name}"

    def as_markdown(self) -> str:
        """The skill as a standalone SKILL.md document (frontmatter + body)."""
        return f"---\nname: {self.name}\ndescription: {self.description}\n---\n\n{self.body}\n"

    def public(self, *, include_body: bool = False) -> dict:
        data = {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "uri": self.uri,
        }
        if include_body:
            data["body"] = self.body
        return data


def parse_skill(text: str, fallback_name: str) -> Skill:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        head, sep, rest = text[3:].partition("\n---")
        if sep:
            body = rest.lstrip("\n")
            for line in head.strip().splitlines():
                key, colon, value = line.partition(":")
                if colon:
                    meta[key.strip().lower()] = value.strip().strip("\"'")
    name = meta.get("name") or fallback_name
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid skill name {name!r} (use lowercase letters, digits, hyphens)")
    return Skill(
        name=name,
        title=meta.get("title") or name.replace("-", " ").capitalize(),
        description=meta.get("description") or "",
        body=body.strip(),
    )


@lru_cache(maxsize=1)
def load_skills() -> dict[str, Skill]:
    """All bundled skills by name — the core skill first, then alphabetical."""
    skills: dict[str, Skill] = {}
    if SKILLS_DIR.is_dir():
        for path in sorted(SKILLS_DIR.glob("*.md")):
            skill = parse_skill(path.read_text(encoding="utf-8"), path.stem)
            skills[skill.name] = skill
    ordered = sorted(skills.values(), key=lambda s: (s.name != CORE_SKILL, s.name))
    return {s.name: s for s in ordered}


def get_skill(name: str) -> Skill | None:
    return load_skills().get((name or "").strip().lower())


def skills_index() -> str:
    """One line per skill, for tool descriptions and server instructions."""
    return "\n".join(f"- {s.name}: {s.description}" for s in load_skills().values())
