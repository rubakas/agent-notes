"""Regression test: validate skips .git/ and node_modules/ by path component,
not by substring match on the entire path string.

Bug: `"node_modules" in str(md_file)` is a substring match, so a directory
named `my-node_modules` was wrongly excluded.  Similarly, `.git` as a substring
could match unrelated path segments on some systems.
Fix: check path *components* only.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

import agent_notes.config as config


def _setup_valid_dist(tmp_path):
    """Create a minimal valid dist layout so validate() finds all required files."""
    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    for d in ["claude", "opencode", "github", "rules"]:
        (fake_dist / d).mkdir(parents=True)

    (fake_dist / "claude" / "CLAUDE.md").write_text("# config\n")
    (fake_dist / "opencode" / "AGENTS.md").write_text("# config\n")
    (fake_dist / "github" / "copilot-instructions.md").write_text("# config\n")
    (fake_dist / "rules" / "code-quality.md").write_text("# config\n")
    (fake_dist / "rules" / "safety.md").write_text("# config\n")
    return fake_dist


def _patches(tmp_path, fake_dist):
    return (
        patch.object(config, "DIST_CLAUDE_DIR", fake_dist / "claude"),
        patch.object(config, "DIST_OPENCODE_DIR", fake_dist / "opencode"),
        patch.object(config, "DIST_GITHUB_DIR", fake_dist / "github"),
        patch.object(config, "DIST_RULES_DIR", fake_dist / "rules"),
        patch.object(config, "ROOT", tmp_path),
        patch("agent_notes.config.find_skill_dirs", return_value=[]),
    )


class TestValidatePathFilter:
    def test_my_node_modules_dir_not_excluded(self, tmp_path, capsys):
        """A dir named my-node_modules must NOT be excluded (not the node_modules component)."""
        fake_dist = _setup_valid_dist(tmp_path)

        # my-node_modules contains the substring "node_modules" but is not the component
        problem_dir = tmp_path / "my-node_modules"
        problem_dir.mkdir()
        (problem_dir / "entry.md").write_text("```python\nno closing fence\n")

        ps = _patches(tmp_path, fake_dist)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
            with pytest.raises(SystemExit) as exc_info:
                from agent_notes.commands.validate import validate
                validate()

        out = capsys.readouterr().out
        # The unclosed block must cause a FAIL → non-zero exit
        assert exc_info.value.code != 0, (
            "Expected non-zero exit because my-node_modules/entry.md has an unclosed "
            "code block, but validate exited 0 — file wrongly excluded by substring check."
        )

    def test_node_modules_dir_is_excluded(self, tmp_path, capsys):
        """A markdown file under an exact node_modules/ component must be skipped."""
        fake_dist = _setup_valid_dist(tmp_path)

        nm_dir = tmp_path / "node_modules"
        nm_dir.mkdir()
        (nm_dir / "some-pkg.md").write_text("```python\nno closing fence\n")

        ps = _patches(tmp_path, fake_dist)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
            with pytest.raises(SystemExit) as exc_info:
                from agent_notes.commands.validate import validate
                validate()

        assert exc_info.value.code == 0, (
            "Expected zero exit because node_modules/some-pkg.md should be skipped."
        )

    def test_dot_git_dir_is_excluded(self, tmp_path, capsys):
        """A markdown file genuinely under .git/ must still be skipped."""
        fake_dist = _setup_valid_dist(tmp_path)

        dot_git_dir = tmp_path / ".git"
        dot_git_dir.mkdir()
        (dot_git_dir / "COMMIT_EDITMSG.md").write_text("```python\nno closing fence\n")

        ps = _patches(tmp_path, fake_dist)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
            with pytest.raises(SystemExit) as exc_info:
                from agent_notes.commands.validate import validate
                validate()

        assert exc_info.value.code == 0, (
            "Expected zero exit because .git/COMMIT_EDITMSG.md should be skipped."
        )
