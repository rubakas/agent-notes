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


# --- Scripts ---

def test_cost_report_script_exists(built_dist):
    assert (built_dist / "scripts" / "cost-report").exists()


def test_cost_report_is_executable(built_dist):
    import stat
    script = built_dist / "scripts" / "cost-report"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR


def test_cost_report_contains_pricing_json(built_dist):
    content = (built_dist / "scripts" / "cost-report").read_text()
    assert '"providers"' in content


def test_cost_report_has_no_placeholder(built_dist):
    content = (built_dist / "scripts" / "cost-report").read_text()
    assert "{{PRICING}}" not in content


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
