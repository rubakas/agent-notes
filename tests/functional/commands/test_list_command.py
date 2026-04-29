"""Functional tests for the list command."""

import pytest
from unittest.mock import patch


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestListClIsPrintsSupportedCLIs:
    def test_list_clis_prints_supported_clis(self, capsys):
        from agent_notes.commands.list import list_clis
        list_clis()

        out = capsys.readouterr().out
        # Must mention at least one well-known CLI
        assert any(cli in out.lower() for cli in ["claude", "opencode", "copilot", "github"])


class TestListSkillsPrintsSkillNames:
    def test_list_skills_prints_skill_names(self, capsys):
        from agent_notes.commands.list import list_skills
        list_skills()

        out = capsys.readouterr().out
        # Output should start the Skills section
        assert "skills" in out.lower() or "Skills" in out


class TestListAgentsPrintsAgentRoster:
    def test_list_agents_prints_agent_roster(self, capsys):
        from agent_notes.commands.list import list_agents
        list_agents()

        out = capsys.readouterr().out
        # The project has known agents; at least one must appear
        assert any(name in out for name in ["lead", "coder", "reviewer", "explorer"])


class TestListUnknownKindErrors:
    def test_list_unknown_kind_errors(self, capsys):
        from agent_notes.commands.list import list_components

        with pytest.raises(SystemExit) as exc_info:
            list_components("nonsense")

        assert exc_info.value.code != 0
        out = capsys.readouterr().out
        assert "nonsense" in out or "unknown" in out.lower()
