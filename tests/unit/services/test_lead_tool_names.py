"""The shared lead text names each backend's own dispatch, resume and todo tools."""
from unittest.mock import patch

import pytest

import agent_notes.config as config_mod
from agent_notes.domain.state import MemoryConfig
from agent_notes.services.rendering import (
    _substitute_tool_names,
    generate_agent_files,
    load_agents_config,
    render_globals,
)


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    root = tmp_path_factory.mktemp("lead_tool_names")
    dist = root / "dist"
    memory = MemoryConfig(backend="local", path="")
    with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(root / "xdg")}), \
         patch.object(config_mod, "DIST_DIR", dist), \
         patch.object(config_mod, "DIST_CLAUDE_DIR", dist / "claude"), \
         patch.object(config_mod, "DIST_OPENCODE_DIR", dist / "opencode"), \
         patch.object(config_mod, "DIST_GITHUB_DIR", dist / "github"), \
         patch("agent_notes.services.user_config.load_user_config", return_value={}):
        generate_agent_files(load_agents_config(), memory=memory)
        render_globals(memory=memory)
    return dist


def test_claude_lead_text_has_no_opencode_tool_names(dist):
    text = (dist / "claude" / "CLAUDE.md").read_text()
    for forbidden in ("todowrite", "`task`", "task_id", "fail silently"):
        assert forbidden not in text, forbidden
    assert "the `Agent` tool" in text
    assert "`SendMessage`" in text


def test_opencode_lead_names_task_and_todowrite(dist):
    text = (dist / "opencode" / "agents" / "lead.md").read_text()
    assert "the `task` tool" in text
    assert "`todowrite`" in text
    assert "task_id" not in text
    assert "if your CLI supports it" in text


def test_no_placeholder_survives_in_any_rendered_file(dist):
    files = [f for f in dist.rglob("*") if f.is_file()]
    assert files
    leaked = [str(f.relative_to(dist)) for f in files if "{{" in f.read_text(errors="replace")]
    assert leaked == []


@pytest.mark.parametrize("backend", ["claude", "opencode", "codex", "copilot", "unknown"])
def test_every_backend_resolves_all_three_placeholders(backend):
    text = "A {{AGENT_TOOL}} B {{RESUME_TOOL}} C\n{{TODO_LINE}}\nD\n"
    out = _substitute_tool_names(text, backend)
    assert "{{" not in out
    assert out.endswith("D\n")


def test_empty_todo_line_leaves_no_blank_line():
    out = _substitute_tool_names("- a\n{{TODO_LINE}}\n- b\n", "claude")
    assert out == "- a\n- b\n"


def test_codex_gets_neutral_wording_and_no_todo_line():
    out = _substitute_tool_names("{{AGENT_TOOL}}|{{RESUME_TOOL}}|\n{{TODO_LINE}}\nx", "codex")
    assert out == "spawn a subagent|steer the same subagent thread|\nx"
