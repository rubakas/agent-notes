"""browser-tester drives the user's Chrome through the claude-in-chrome MCP server,
so it exists for Claude Code only: the exclusion must hold in the registry and in the build."""
from unittest.mock import patch

import agent_notes.config as config_mod
from agent_notes.registries.agent_registry import load_agent_registry
from agent_notes.services.rendering import generate_agent_files, load_agents_config


def _render_all(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    dist = tmp_path / "dist"
    with patch.object(config_mod, "DIST_DIR", dist), \
         patch("agent_notes.services.user_config.load_user_config", return_value={}):
        generate_agent_files(load_agents_config())
    return dist


def _frontmatter(path):
    text = path.read_text()
    return text.split("---", 2)[1]


class TestBrowserTesterRegistry:
    def test_excluded_from_opencode_and_codex_only(self):
        agent = load_agent_registry().get("browser-tester")

        assert agent.excluded_from("opencode") is True
        assert agent.excluded_from("codex") is True
        assert agent.excluded_from("claude") is False


_CHROME_TOOLS = [
    "mcp__claude-in-chrome__" + name
    for name in (
        "list_connected_browsers", "tabs_context_mcp", "tabs_create_mcp", "tabs_close_mcp",
        "navigate", "computer", "read_page", "find", "get_page_text", "form_input",
        "javascript_tool", "read_console_messages", "read_network_requests", "resize_window",
    )
]


class TestBrowserTesterRendering:
    def test_claude_tools_are_the_exact_least_privilege_list(self, tmp_path, monkeypatch):
        dist = _render_all(tmp_path, monkeypatch)

        path = dist / "claude" / "agents" / "browser-tester.md"
        assert path.exists()
        tools_line = next(
            line for line in _frontmatter(path).splitlines() if line.startswith("tools:")
        )
        tools = [t.strip() for t in tools_line.split(":", 1)[1].split(",")]
        assert tools == ["ToolSearch", "Read", "Write"] + _CHROME_TOOLS

    def test_has_no_persistent_memory(self, tmp_path, monkeypatch):
        dist = _render_all(tmp_path, monkeypatch)

        path = dist / "claude" / "agents" / "browser-tester.md"
        assert not any(
            line.startswith("memory:") for line in _frontmatter(path).splitlines()
        )

    def test_prompt_loads_exactly_the_granted_chrome_tools(self, tmp_path, monkeypatch):
        dist = _render_all(tmp_path, monkeypatch)

        body = (dist / "claude" / "agents" / "browser-tester.md").read_text()
        select = next(line for line in body.splitlines() if "`select:" in line)
        loaded = select.split("`select:", 1)[1].split("`", 1)[0].split(",")
        assert sorted(loaded) == sorted(_CHROME_TOOLS)

    def test_not_rendered_for_opencode_or_codex(self, tmp_path, monkeypatch):
        dist = _render_all(tmp_path, monkeypatch)

        assert (dist / "claude" / "agents" / "browser-tester.md").exists()
        assert not (dist / "opencode" / "agents" / "browser-tester.md").exists()
        assert not (dist / "codex" / "agents" / "browser-tester.toml").exists()
        assert (dist / "opencode" / "agents" / "coder.md").exists()
        assert (dist / "codex" / "agents" / "coder.toml").exists()
