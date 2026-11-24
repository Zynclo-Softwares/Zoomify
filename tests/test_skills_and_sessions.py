"""Tests for the skills loader and the zoom session store."""

from __future__ import annotations

import pytest

from zoomify import session as session_mod
from zoomify import skills
from zoomify.session import SessionStore
from zoomify.tools import ImageState


def test_bundled_skills_are_well_formed():
    loaded = skills.load_skills()
    assert list(loaded)[0] == skills.CORE_SKILL
    assert len(loaded) >= 4
    for skill in loaded.values():
        assert skill.title and skill.description
        assert skill.body.startswith("# ")
        assert skill.uri == f"zoomify://skills/{skill.name}"
        assert len(skill.description) < 200
    assert skills.get_skill(" Zoom-Basics ").name == "zoom-basics"
    assert skills.get_skill("missing") is None
    assert "- zoom-basics:" in skills.skills_index()


def test_parse_skill_frontmatter_and_fallbacks():
    skill = skills.parse_skill(
        '---\nname: site-plans\ntitle: Site plans\ndescription: "Parcels: and lots"\n---\n\n# Body\n',
        "ignored",
    )
    assert (skill.name, skill.title, skill.description) == (
        "site-plans",
        "Site plans",
        "Parcels: and lots",
    )
    assert skill.body == "# Body"
    assert skill.as_markdown().startswith(
        "---\nname: site-plans\ndescription: Parcels: and lots\n---"
    )

    bare = skills.parse_skill("# Just a body", "my-skill")
    assert (bare.name, bare.title) == ("my-skill", "My skill")

    with pytest.raises(ValueError, match="Invalid skill name"):
        skills.parse_skill("# x", "Bad Name")


def test_new_skill_file_is_picked_up(tmp_path, monkeypatch):
    (tmp_path / "site-plans.md").write_text(
        "---\nname: site-plans\ndescription: Parcels and lots\n---\n# Site plans\n"
    )
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    skills.load_skills.cache_clear()
    try:
        assert list(skills.load_skills()) == ["site-plans"]
        from zoomify.mcp_server import build_mcp

        assert "site-plans" in build_mcp().instructions
    finally:
        skills.load_skills.cache_clear()


def test_session_store_lifecycle(small_img, monkeypatch):
    s = SessionStore()
    state = ImageState.from_image(small_img)
    first, evicted = s.create("u1", state, label="a", max_open=2)
    assert first.id.startswith("zs_") and evicted == []
    assert s.get("u1", first.id) is first
    assert s.get("u2", first.id) is None

    second, _ = s.create("u1", state, label="b", max_open=2)
    s.get("u1", first.id)  # touch: first becomes the most recently used
    _, evicted = s.create("u1", state, label="c", max_open=2)
    assert evicted == [second.id]
    assert s.count("u1") == 2

    assert s.delete("u2", first.id) is False
    assert s.delete("u1", first.id) is True

    now = session_mod.time.time()
    monkeypatch.setattr(session_mod.time, "time", lambda: now + session_mod.SESSION_TTL_SECONDS + 5)
    assert s.count("u1") == 0
