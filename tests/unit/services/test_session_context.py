"""Tests for agent_notes.services.session_context — _render_skills_catalog and render_context."""
import pytest
from pathlib import Path

from agent_notes.domain.skill import Skill
from agent_notes.services.session_context import _render_skills_catalog, render_context


def _skill(name: str, description: str = "", group: str | None = None) -> Skill:
    """Build a minimal Skill fixture without touching the filesystem."""
    return Skill(name=name, path=Path("/fake") / name, description=description, group=group)


class TestRenderSkillsCatalog:
    def test_empty_list_returns_empty_string(self):
        assert _render_skills_catalog([]) == ""

    def test_none_equivalent_empty_handled_by_caller(self):
        """render_context passes [] when skills is falsy; catalog itself only receives lists."""
        assert _render_skills_catalog([]) == ""

    def test_single_skill_renders_name_and_description(self):
        result = _render_skills_catalog([_skill("brainstorming", "Explore multiple approaches")])
        assert "/brainstorming" in result
        assert "Explore multiple approaches" in result

    def test_single_skill_uses_em_dash_separator(self):
        result = _render_skills_catalog([_skill("brainstorming", "Explore multiple approaches")])
        assert "— Explore multiple approaches" in result

    def test_multiple_skills_sorted_alphabetically(self):
        skills = [
            _skill("zebra", "Last alphabetically"),
            _skill("alpha", "First alphabetically"),
            _skill("middle", "In between"),
        ]
        result = _render_skills_catalog(skills)
        alpha_pos = result.index("/alpha")
        middle_pos = result.index("/middle")
        zebra_pos = result.index("/zebra")
        assert alpha_pos < middle_pos < zebra_pos

    def test_header_line_is_present(self):
        result = _render_skills_catalog([_skill("foo", "bar")])
        assert "**Skills**" in result
        assert "/skill-name" in result

    def test_skill_with_no_description_still_renders(self):
        result = _render_skills_catalog([_skill("silent", description="")])
        assert "/silent" in result

    def test_each_skill_appears_on_its_own_line(self):
        skills = [_skill("aaa", "desc a"), _skill("bbb", "desc b")]
        lines = _render_skills_catalog(skills).splitlines()
        skill_lines = [l for l in lines if l.startswith("- /")]
        assert len(skill_lines) == 2

    def test_skills_with_groups_are_still_rendered(self):
        skills = [_skill("git", "Git workflow helper", group="scm")]
        result = _render_skills_catalog(skills)
        assert "/git" in result
        assert "Git workflow helper" in result


class TestRenderContext:
    def test_version_substituted(self):
        result = render_context(agents=[], version="9.9.9")
        assert "9.9.9" in result
        assert "{{version}}" not in result

    def test_agents_list_substituted_with_provided_agents(self):
        result = render_context(agents=["coder", "explorer"], version="1.0")
        assert "- coder" in result
        assert "- explorer" in result
        assert "{{agents_list}}" not in result

    def test_empty_agents_uses_fallback_message(self):
        result = render_context(agents=[], version="1.0")
        assert "~/.claude/agents/" in result
        assert "{{agents_list}}" not in result

    def test_agents_sorted_alphabetically(self):
        result = render_context(agents=["zebra", "alpha"], version="1.0")
        alpha_pos = result.index("- alpha")
        zebra_pos = result.index("- zebra")
        assert alpha_pos < zebra_pos

    def test_skills_none_removes_placeholder(self):
        result = render_context(agents=[], version="1.0", skills=None)
        assert "{{skills_catalog}}" not in result

    def test_skills_empty_list_removes_placeholder(self):
        result = render_context(agents=[], version="1.0", skills=[])
        assert "{{skills_catalog}}" not in result

    def test_skills_empty_list_injects_no_catalog_text(self):
        result = render_context(agents=[], version="1.0", skills=[])
        assert "**Skills**" not in result

    def test_skills_provided_injects_catalog(self):
        skills = [_skill("brainstorming", "Explore multiple approaches")]
        result = render_context(agents=[], version="1.0", skills=skills)
        assert "**Skills**" in result
        assert "/brainstorming" in result
        assert "Explore multiple approaches" in result

    def test_skills_placeholder_replaced_when_skills_provided(self):
        skills = [_skill("caveman", "Ultra-compressed communication")]
        result = render_context(agents=[], version="1.0", skills=skills)
        assert "{{skills_catalog}}" not in result

    def test_no_literal_placeholders_remain_with_full_render(self):
        skills = [_skill("git", "Git helper"), _skill("brainstorming", "Explore ideas")]
        result = render_context(agents=["coder", "reviewer"], version="2.0", skills=skills)
        assert "{{version}}" not in result
        assert "{{agents_list}}" not in result
        assert "{{skills_catalog}}" not in result

    def test_full_render_contains_all_three_sections(self):
        """version, agents, and skills all appear together in a full render."""
        skills = [_skill("caveman", "Compressed comms")]
        result = render_context(agents=["coder"], version="3.1.4", skills=skills)
        assert "3.1.4" in result
        assert "- coder" in result
        assert "/caveman" in result
        assert "Compressed comms" in result

    def test_default_skills_param_is_none(self):
        """render_context(agents, version) with no skills kwarg must not raise."""
        result = render_context(agents=["coder"], version="1.0")
        assert "{{skills_catalog}}" not in result
        assert "1.0" in result
