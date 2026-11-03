"""The restated rule block lands in every agent body, and the Discoveries relay
renders only on the obsidian backend."""
from unittest.mock import patch

import pytest

import agent_notes.config as config_mod
from agent_notes.config import AGENTS_DIR
from agent_notes.domain.state import MemoryConfig
from agent_notes.services.rendering import generate_agent_files, load_agents_config

RULES = (AGENTS_DIR / "shared" / "agent_rules.md").read_text().strip()
DISCOVERY_WRITERS = (
    "coder", "test-writer", "test-runner", "devops", "tech-writer", "integrations", "refactorer",
)


def _render(tmp_path, monkeypatch, backend, vault=None):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    dist = tmp_path / "dist"
    memory = MemoryConfig(backend=backend, path=str(vault) if vault else "")
    with patch.object(config_mod, "DIST_DIR", dist), \
         patch("agent_notes.services.user_config.load_user_config", return_value={}):
        generate_agent_files(load_agents_config(), memory=memory)
    return dist


@pytest.fixture
def local_dist(tmp_path, monkeypatch):
    return _render(tmp_path, monkeypatch, "local")


@pytest.fixture
def obsidian_dist(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    return _render(tmp_path / "obs", monkeypatch, "obsidian", vault)


def test_rule_block_is_at_most_25_lines():
    assert len(RULES.splitlines()) <= 25


def test_claude_coder_restates_credentials_and_attribution(local_dist):
    text = (local_dist / "claude" / "agents" / "coder.md").read_text()
    assert "Credentials — absolute" in text and "Never read, open, cat, grep" in text
    assert "No AI attribution — absolute" in text and "Co-Authored-By" in text


def test_every_claude_agent_gets_the_block_exactly_once(local_dist):
    files = sorted((local_dist / "claude" / "agents").glob("*.md"))
    assert files
    for f in files:
        text = f.read_text()
        assert text.count(RULES) == 1, f.name
        assert "<!-- include:" not in text, f.name


def test_opencode_and_codex_agents_get_the_block_once(local_dist):
    opencode = sorted((local_dist / "opencode" / "agents").glob("*.md"))
    codex = sorted((local_dist / "codex" / "agents").iterdir())
    assert opencode and codex
    for f in opencode:
        expected = 0 if f.stem == "lead" else 1
        assert f.read_text().count(RULES) == expected, f.name
    for f in codex:
        assert "Rules that always apply" in f.read_text(), f.name


@pytest.mark.parametrize("name", DISCOVERY_WRITERS)
def test_local_backend_has_no_discoveries_section(local_dist, name):
    text = (local_dist / "claude" / "agents" / f"{name}.md").read_text()
    assert "## Discoveries" not in text
    assert "Report discoveries" not in text


@pytest.mark.parametrize("name", DISCOVERY_WRITERS)
def test_obsidian_backend_keeps_discoveries_section(obsidian_dist, name):
    text = (obsidian_dist / "claude" / "agents" / f"{name}.md").read_text()
    assert "Report discoveries" in text
    assert "`## Discoveries`" in text
    assert text.index("Rules that always apply") < text.index("Report discoveries")


def test_local_render_leaves_no_run_of_blank_lines_at_the_end(local_dist):
    text = (local_dist / "claude" / "agents" / "coder.md").read_text()
    assert not text.endswith("\n\n\n")
