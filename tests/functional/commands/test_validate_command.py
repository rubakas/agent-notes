"""Functional tests for the validate command."""

import pytest
from pathlib import Path
from unittest.mock import patch

import agent_notes.config as config


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestValidatePassesOnCleanData:
    def test_validate_passes_on_clean_data(self, tmp_path, capsys, built_dist):
        """validate() exits 0 when run against the real built dist tree."""
        with pytest.raises(SystemExit) as exc_info:
            from agent_notes.commands.validate import validate
            validate()

        # exit(0) or exit(1) — pass only if no errors
        out = capsys.readouterr().out
        # If there were errors the summary says "error(s)"; clean run says "All checks passed"
        assert exc_info.value.code == 0, (
            f"validate exited {exc_info.value.code}. Output:\n{out}"
        )


def _patch_validate_dirs(tmp_path, fake_dist):
    """Return a context manager patching all config constants validate() uses."""
    fake_claude = fake_dist / "claude"
    fake_opencode = fake_dist / "opencode"
    fake_github = fake_dist / "github"
    fake_rules = fake_dist / "rules"
    return (
        patch.object(config, "DIST_CLAUDE_DIR", fake_claude),
        patch.object(config, "DIST_OPENCODE_DIR", fake_opencode),
        patch.object(config, "DIST_GITHUB_DIR", fake_github),
        patch.object(config, "DIST_RULES_DIR", fake_rules),
        # ROOT is used for file_path.relative_to(ROOT) and rglob — point to tmp_path
        patch.object(config, "ROOT", tmp_path),
        patch("agent_notes.config.find_skill_dirs", return_value=[]),
    )


class TestValidateReportsMissingRequiredYamlField:
    def test_validate_reports_missing_required_yaml_field(self, tmp_path, monkeypatch, capsys):
        """An agent file missing 'description' produces an error mentioning the field."""
        fake_dist = tmp_path / "dist"
        fake_dist.mkdir()
        agents_dir = fake_dist / "claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Write an agent missing 'description'
        (agents_dir / "bad-agent.md").write_text(
            "---\nname: bad-agent\nmodel: claude-sonnet-4-5\n---\n# body\n"
        )

        patches = _patch_validate_dirs(tmp_path, fake_dist)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            with pytest.raises(SystemExit):
                from agent_notes.commands.validate import validate
                validate()

        out = capsys.readouterr().out
        assert "description" in out
        assert "missing" in out.lower() or "fail" in out.lower()


class TestValidateExitsNonzeroOnInvalid:
    def test_validate_exits_nonzero_on_invalid(self, tmp_path, monkeypatch, capsys):
        """Bad dist → validate() exits with a non-zero code."""
        fake_dist = tmp_path / "dist"
        fake_dist.mkdir()
        agents_dir = fake_dist / "claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Agent with no frontmatter at all
        (agents_dir / "broken.md").write_text("# just a body, no frontmatter\n")

        patches = _patch_validate_dirs(tmp_path, fake_dist)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            with pytest.raises(SystemExit) as exc_info:
                from agent_notes.commands.validate import validate
                validate()

        assert exc_info.value.code != 0
