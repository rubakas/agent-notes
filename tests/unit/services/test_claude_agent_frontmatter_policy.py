"""Frontmatter policy for every Claude Code agent: it parses, drops CLAUDE.md,
never lists the Agent tool, and the analysis agents are read-only leaves."""
from unittest.mock import patch

import pytest
import yaml

import agent_notes.config as config_mod
from agent_notes.services.rendering import generate_agent_files, load_agents_config

ANALYSIS_AGENTS = (
    "reviewer", "security-auditor", "system-auditor",
    "database-specialist", "performance-profiler", "api-reviewer",
)
ANALYSIS_TOOLS = "Read, Grep, Glob, Bash, WebFetch"


@pytest.fixture(scope="module")
def claude_frontmatter(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("claude-policy")
    dist = tmp_path / "dist"
    with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}), \
         patch.object(config_mod, "DIST_DIR", dist), \
         patch("agent_notes.services.user_config.load_user_config", return_value={}):
        generate_agent_files(load_agents_config())
    files = sorted((dist / "claude" / "agents").glob("*.md"))
    assert files
    return {f.stem: yaml.safe_load(f.read_text().split("---", 2)[1]) for f in files}


def test_lead_is_not_rendered_for_claude(claude_frontmatter):
    assert "lead" not in claude_frontmatter


def test_every_frontmatter_parses_with_a_string_description(claude_frontmatter):
    for name, fm in claude_frontmatter.items():
        assert fm["name"] == name
        assert isinstance(fm["description"], str) and fm["description"], name


def test_every_agent_omits_claude_md(claude_frontmatter):
    for name, fm in claude_frontmatter.items():
        assert fm.get("omitClaudeMd") is True, name


def test_no_agent_can_spawn_agents(claude_frontmatter):
    for name, fm in claude_frontmatter.items():
        tools = [t.strip().split("(")[0] for t in str(fm.get("tools", "")).split(",")]
        assert "Agent" not in tools, name


@pytest.mark.parametrize("name", ANALYSIS_AGENTS)
def test_analysis_agents_are_read_only_with_no_memory(claude_frontmatter, name):
    fm = claude_frontmatter[name]
    assert fm["tools"] == ANALYSIS_TOOLS
    assert "memory" not in fm
    assert "disallowedTools" not in fm


def test_browser_tester_runs_in_background(claude_frontmatter):
    assert claude_frontmatter["browser-tester"]["background"] is True
