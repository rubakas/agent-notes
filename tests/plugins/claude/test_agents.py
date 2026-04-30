"""Parametrized tests for every agent file in dist/claude/agents/."""
import pytest
from pathlib import Path

from agent_notes.config import DIST_DIR

_VALID_MODEL_KEYWORDS = {"haiku", "sonnet", "opus", "claude", "gpt", "gemini"}

_CLAUDE_AGENTS_DIR = DIST_DIR / "claude" / "agents"


def _agent_files():
    if not _CLAUDE_AGENTS_DIR.is_dir():
        return []
    return sorted(_CLAUDE_AGENTS_DIR.glob("*.md"))


def _parse_frontmatter(text: str) -> dict:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    result = {}
    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"\'')
    return result


AGENT_FILES = _agent_files()

if not AGENT_FILES:
    raise RuntimeError(
        f"test_agents.py: no agent files found under {_CLAUDE_AGENTS_DIR}. "
        f"The session-scoped built_dist fixture should have populated it. "
        f"Run `python3 -m agent_notes build` manually if running outside pytest."
    )


@pytest.fixture(scope="module", autouse=True)
def require_built_dist(built_dist):
    """Ensure the build has run before collecting agent files."""
    pass


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_file_non_empty(agent_file):
    assert agent_file.stat().st_size > 0, f"{agent_file.name} is empty"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_has_frontmatter_markers(agent_file):
    text = agent_file.read_text()
    lines = text.split("\n")
    assert lines[0].strip() == "---", f"{agent_file.name} does not start with ---"
    has_close = any(line.strip() == "---" for line in lines[1:])
    assert has_close, f"{agent_file.name} has no closing ---"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_frontmatter_has_name(agent_file):
    text = agent_file.read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("name", "").strip(), f"{agent_file.name} missing 'name' in frontmatter"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_frontmatter_has_description(agent_file):
    text = agent_file.read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("description", "").strip(), f"{agent_file.name} missing 'description' in frontmatter"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_frontmatter_model_is_valid(agent_file):
    text = agent_file.read_text()
    fm = _parse_frontmatter(text)
    model = fm.get("model", "").strip().lower()
    assert model, f"{agent_file.name} missing 'model' in frontmatter"
    assert any(kw in model for kw in _VALID_MODEL_KEYWORDS), (
        f"{agent_file.name}: model '{model}' does not match any known keyword"
    )


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_frontmatter_has_tools(agent_file):
    text = agent_file.read_text()
    fm = _parse_frontmatter(text)
    has_tools = fm.get("tools", "").strip()
    has_disallowed = fm.get("disallowedTools", "").strip()
    assert has_tools or has_disallowed, (
        f"{agent_file.name} missing both 'tools' and 'disallowedTools' in frontmatter"
    )
