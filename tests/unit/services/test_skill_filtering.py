"""Tests for _filter_skills_by_backend in agent_notes.services.installer."""
from pathlib import Path

from agent_notes.domain.skill import Skill
from agent_notes.services.installer import _filter_skills_by_backend


def _make_skill(name: str, requires_memory=None) -> Skill:
    return Skill(
        name=name,
        path=Path(f"/fake/{name}"),
        description=f"test {name}",
        requires_memory=requires_memory,
    )


class TestFilterSkillsByBackend:
    def test_skill_without_requires_memory_always_visible(self):
        skills = [_make_skill("git")]
        assert len(_filter_skills_by_backend(skills, "none")) == 1
        assert len(_filter_skills_by_backend(skills, "local")) == 1
        assert len(_filter_skills_by_backend(skills, "obsidian")) == 1
        assert len(_filter_skills_by_backend(skills, "wiki")) == 1

    def test_skill_with_single_backend_requirement(self):
        skills = [_make_skill("wiki-only", requires_memory="wiki")]
        assert len(_filter_skills_by_backend(skills, "wiki")) == 1
        assert len(_filter_skills_by_backend(skills, "obsidian")) == 0
        assert len(_filter_skills_by_backend(skills, "local")) == 0
        assert len(_filter_skills_by_backend(skills, "none")) == 0

    def test_skill_with_multiple_backend_requirements(self):
        skills = [_make_skill("ingest", requires_memory="obsidian,wiki")]
        assert len(_filter_skills_by_backend(skills, "obsidian")) == 1
        assert len(_filter_skills_by_backend(skills, "wiki")) == 1
        assert len(_filter_skills_by_backend(skills, "local")) == 0
        assert len(_filter_skills_by_backend(skills, "none")) == 0

    def test_mixed_skills_filtered_correctly(self):
        skills = [
            _make_skill("git"),
            _make_skill("ingest", requires_memory="obsidian,wiki"),
            _make_skill("obsidian-memory", requires_memory="obsidian,wiki"),
            _make_skill("wiki-only", requires_memory="wiki"),
        ]
        # local backend: only git visible
        result = _filter_skills_by_backend(skills, "local")
        assert [s.name for s in result] == ["git"]

        # obsidian backend: git + ingest + obsidian-memory
        result = _filter_skills_by_backend(skills, "obsidian")
        assert [s.name for s in result] == ["git", "ingest", "obsidian-memory"]

        # wiki backend: all four
        result = _filter_skills_by_backend(skills, "wiki")
        assert [s.name for s in result] == ["git", "ingest", "obsidian-memory", "wiki-only"]

    def test_empty_skills_list(self):
        assert _filter_skills_by_backend([], "wiki") == []

    def test_whitespace_in_requires_memory_handled(self):
        skills = [_make_skill("spaced", requires_memory="obsidian , wiki")]
        assert len(_filter_skills_by_backend(skills, "obsidian")) == 1
        assert len(_filter_skills_by_backend(skills, "wiki")) == 1
        assert len(_filter_skills_by_backend(skills, "local")) == 0
