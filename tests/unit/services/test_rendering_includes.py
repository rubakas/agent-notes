"""Tests for expand_includes and its integration with render_globals."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_notes.services.rendering import expand_includes


class TestExpandIncludes:
    def test_substitutes_directive_with_file_content(self, tmp_path):
        """expand_includes() replaces <!-- include: NAME --> with file content."""
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "my_section.md").write_text("## My Section\n\nSome text here.\n")

        text = "Before\n<!-- include: my_section -->\nAfter"
        result = expand_includes(text, shared)
        assert "## My Section" in result
        assert "Some text here." in result
        assert "<!-- include: my_section -->" not in result
        assert "Before" in result
        assert "After" in result

    def test_returns_unchanged_if_shared_dir_missing(self, tmp_path):
        """expand_includes() returns text unchanged when shared_dir doesn't exist."""
        missing = tmp_path / "nonexistent"
        text = "<!-- include: something -->"
        assert expand_includes(text, missing) == text

    def test_raises_for_unknown_include(self, tmp_path):
        """expand_includes() raises ValueError for a directive with no matching file."""
        shared = tmp_path / "shared"
        shared.mkdir()
        with pytest.raises(ValueError, match="Unknown include: missing_file"):
            expand_includes("<!-- include: missing_file -->", shared)


class TestRenderGlobalsExpandsIncludes:
    def test_render_globals_expands_includes_in_claude_md(self, tmp_path):
        """render_globals() expands <!-- include: NAME --> directives in global-claude.md."""
        import agent_notes.config as config_mod

        # Set up a fake AGENTS_DIR with shared/cost_reporting.md
        fake_agents_dir = tmp_path / "agents"
        shared_dir = fake_agents_dir / "shared"
        shared_dir.mkdir(parents=True)
        (shared_dir / "cost_reporting.md").write_text(
            "## Cost reporting\n\nRun cost-report here.\n"
        )

        # Fake global-claude.md with an include directive
        fake_claude_md = tmp_path / "global-claude.md"
        fake_claude_md.write_text(
            "# Global\n\n{{MEMORY_INSTRUCTIONS}}\n\n<!-- include: cost_reporting -->\n\nEnd.\n"
        )

        # Fake dist directories
        dist_claude_dir = tmp_path / "dist" / "claude"
        dist_claude_dir.mkdir(parents=True)
        dist_opencode_dir = tmp_path / "dist" / "opencode"
        dist_opencode_dir.mkdir(parents=True)
        dist_github_dir = tmp_path / "dist" / ".github"
        dist_github_dir.mkdir(parents=True)

        # Fake opencode and copilot globals (no includes)
        fake_opencode_md = tmp_path / "global-opencode.md"
        fake_opencode_md.write_text("opencode content\n")
        fake_copilot_md = tmp_path / "global-copilot.md"
        fake_copilot_md.write_text("copilot content\n")

        with patch.object(config_mod, "AGENTS_DIR", fake_agents_dir), \
             patch.object(config_mod, "GLOBAL_CLAUDE_MD", fake_claude_md), \
             patch.object(config_mod, "GLOBAL_OPENCODE_MD", fake_opencode_md), \
             patch.object(config_mod, "GLOBAL_COPILOT_MD", fake_copilot_md), \
             patch.object(config_mod, "DIST_CLAUDE_DIR", dist_claude_dir), \
             patch.object(config_mod, "DIST_OPENCODE_DIR", dist_opencode_dir), \
             patch.object(config_mod, "DIST_GITHUB_DIR", dist_github_dir), \
             patch(
                 "agent_notes.services.user_config.load_user_config",
                 return_value={"cost_report_enabled": True},
             ):
            from agent_notes.services.rendering import render_globals
            render_globals()

        output = (dist_claude_dir / "CLAUDE.md").read_text()
        assert "## Cost reporting" in output
        assert "Run cost-report here." in output
        assert "<!-- include: cost_reporting -->" not in output

    def test_render_globals_omits_cost_reporting_when_disabled(self, tmp_path):
        """render_globals() skips cost_reporting include when cost_report_enabled is False."""
        import agent_notes.config as config_mod

        fake_agents_dir = tmp_path / "agents"
        shared_dir = fake_agents_dir / "shared"
        shared_dir.mkdir(parents=True)
        (shared_dir / "cost_reporting.md").write_text(
            "## Cost reporting\n\nRun cost-report here.\n"
        )

        fake_claude_md = tmp_path / "global-claude.md"
        fake_claude_md.write_text(
            "# Global\n\n{{MEMORY_INSTRUCTIONS}}\n\n<!-- include: cost_reporting -->\n\nEnd.\n"
        )

        dist_claude_dir = tmp_path / "dist" / "claude"
        dist_claude_dir.mkdir(parents=True)
        dist_opencode_dir = tmp_path / "dist" / "opencode"
        dist_opencode_dir.mkdir(parents=True)
        dist_github_dir = tmp_path / "dist" / ".github"
        dist_github_dir.mkdir(parents=True)

        fake_opencode_md = tmp_path / "global-opencode.md"
        fake_opencode_md.write_text("opencode content\n")
        fake_copilot_md = tmp_path / "global-copilot.md"
        fake_copilot_md.write_text("copilot content\n")

        with patch.object(config_mod, "AGENTS_DIR", fake_agents_dir), \
             patch.object(config_mod, "GLOBAL_CLAUDE_MD", fake_claude_md), \
             patch.object(config_mod, "GLOBAL_OPENCODE_MD", fake_opencode_md), \
             patch.object(config_mod, "GLOBAL_COPILOT_MD", fake_copilot_md), \
             patch.object(config_mod, "DIST_CLAUDE_DIR", dist_claude_dir), \
             patch.object(config_mod, "DIST_OPENCODE_DIR", dist_opencode_dir), \
             patch.object(config_mod, "DIST_GITHUB_DIR", dist_github_dir), \
             patch(
                 "agent_notes.services.user_config.load_user_config",
                 return_value={"cost_report_enabled": False},
             ):
            from agent_notes.services.rendering import render_globals
            render_globals()

        output = (dist_claude_dir / "CLAUDE.md").read_text()
        assert "## Cost reporting" not in output
        assert "Run cost-report here." not in output
        assert "<!-- include: cost_reporting -->" not in output


class TestGenerateAgentFilesExpandsIncludes:
    """Verify per-agent prompt rendering honours cost_report_enabled via skip set."""

    def _make_env(self, tmp_path):
        """Set up a minimal fake AGENTS_DIR with a lead.md containing the include."""
        fake_agents_dir = tmp_path / "agents"
        shared_dir = fake_agents_dir / "shared"
        shared_dir.mkdir(parents=True)
        (shared_dir / "cost_reporting.md").write_text(
            "## Cost reporting\n\nRun cost-report here.\n"
        )
        (fake_agents_dir / "lead.md").write_text(
            "# Lead\n\n<!-- include: cost_reporting -->\n\nEnd.\n"
        )
        return fake_agents_dir

    def _call_generate(self, fake_agents_dir, cost_report_enabled):
        import agent_notes.config as config_mod
        from agent_notes.services.rendering import generate_agent_files, expand_includes

        agents_config = {"lead": {}}
        tiers = {}

        # Registry returns no backends — prevents file I/O while still exercising
        # the expand_includes call that happens before the backend loop.
        fake_registry = MagicMock()
        fake_registry.all.return_value = []

        captured_calls = []

        def spying_expand_includes(text, shared_dir, skip=None):
            result = expand_includes(text, shared_dir, skip=skip)
            captured_calls.append({"text": text, "skip": skip, "result": result})
            return result

        with patch.object(config_mod, "AGENTS_DIR", fake_agents_dir), \
             patch(
                 "agent_notes.registries.cli_registry.load_registry",
                 return_value=fake_registry,
             ), \
             patch(
                 "agent_notes.services.user_config.load_user_config",
                 return_value={"cost_report_enabled": cost_report_enabled},
             ), \
             patch(
                 "agent_notes.services.rendering.expand_includes",
                 side_effect=spying_expand_includes,
             ):
            generate_agent_files(agents_config, tiers)

        return captured_calls

    def test_per_agent_includes_cost_reporting_when_enabled(self, tmp_path):
        """generate_agent_files() expands cost_reporting include when cost_report_enabled is True."""
        fake_agents_dir = self._make_env(tmp_path)
        calls = self._call_generate(fake_agents_dir, cost_report_enabled=True)

        assert calls, "expand_includes was not called for the agent prompt"
        result = calls[0]["result"]
        assert "## Cost reporting" in result
        assert "Run cost-report here." in result
        assert "<!-- include: cost_reporting -->" not in result
        assert calls[0]["skip"] == set()

    def test_per_agent_omits_cost_reporting_when_disabled(self, tmp_path):
        """generate_agent_files() skips cost_reporting include when cost_report_enabled is False."""
        fake_agents_dir = self._make_env(tmp_path)
        calls = self._call_generate(fake_agents_dir, cost_report_enabled=False)

        assert calls, "expand_includes was not called for the agent prompt"
        result = calls[0]["result"]
        assert "## Cost reporting" not in result
        assert "Run cost-report here." not in result
        assert "<!-- include: cost_reporting -->" not in result
        assert calls[0]["skip"] == {"cost_reporting"}
