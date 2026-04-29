"""Integration tests that verify real build output in dist/."""
import pytest
from pathlib import Path


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from markdown text. Returns dict of key/value strings."""
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
            result[key.strip()] = value.strip()
    return result


# --- Directory structure ---

def test_claude_agents_dir_exists(built_dist):
    assert (built_dist / "claude" / "agents").is_dir()


def test_claude_agents_has_enough_files(built_dist):
    files = list((built_dist / "claude" / "agents").glob("*.md"))
    assert len(files) >= 15


def test_opencode_agents_dir_exists(built_dist):
    assert (built_dist / "opencode" / "agents").is_dir()


def test_opencode_agents_has_files(built_dist):
    files = list((built_dist / "opencode" / "agents").glob("*.md"))
    assert len(files) > 0


def test_skills_dir_exists(built_dist):
    assert (built_dist / "skills").is_dir()


def test_skills_has_enough_subdirs(built_dist):
    subdirs = [p for p in (built_dist / "skills").iterdir() if p.is_dir()]
    assert len(subdirs) >= 30


def test_rules_dir_exists(built_dist):
    assert (built_dist / "rules").is_dir()


def test_rules_has_markdown_files(built_dist):
    files = list((built_dist / "rules").glob("*.md"))
    assert len(files) >= 1


# --- cost-report entry point ---

def test_cost_report_entry_point_registered():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    from pathlib import Path
    pyproject = Path(__file__).parents[3] / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    scripts = data["project"]["scripts"]
    assert scripts.get("cost-report") == "agent_notes.scripts.cost_report:main"


def test_cost_report_module_imports():
    from agent_notes.scripts import cost_report
    assert callable(cost_report.main)


def test_pricing_yaml_loads():
    from agent_notes.scripts import _pricing
    data = _pricing._load()
    assert "baseline" in data
    assert "providers" in data


def test_normalize_model_dashed_to_dotted():
    from agent_notes.scripts import _pricing
    assert _pricing.normalize_model("claude-opus-4-7") == "claude-opus-4.7"
    assert _pricing.normalize_model("claude-sonnet-4-6") == "claude-sonnet-4.6"


# --- Specific agent files ---

def test_coder_md_exists(built_dist):
    assert (built_dist / "claude" / "agents" / "coder.md").exists()


def test_reviewer_md_exists(built_dist):
    assert (built_dist / "claude" / "agents" / "reviewer.md").exists()


def test_coder_frontmatter_name(built_dist):
    text = (built_dist / "claude" / "agents" / "coder.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("name") == "coder"


def test_coder_frontmatter_description(built_dist):
    text = (built_dist / "claude" / "agents" / "coder.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("description", "").strip()


def test_coder_frontmatter_model(built_dist):
    text = (built_dist / "claude" / "agents" / "coder.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("model", "").strip()


def test_coder_frontmatter_tools(built_dist):
    text = (built_dist / "claude" / "agents" / "coder.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("tools", "").strip()


# --- Global config file ---

def test_claude_md_exists(built_dist):
    assert (built_dist / "claude" / "CLAUDE.md").exists()


def test_claude_md_is_non_empty(built_dist):
    content = (built_dist / "claude" / "CLAUDE.md").read_text()
    assert len(content.strip()) > 0
