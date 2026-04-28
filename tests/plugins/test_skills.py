"""Parametrized tests for every skill directory in data/skills/."""
import pytest
from pathlib import Path

from agent_notes.config import SKILLS_DIR


def _skill_dirs():
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())


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


SKILL_DIRS = _skill_dirs()


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_md_exists(skill_dir):
    assert (skill_dir / "SKILL.md").exists(), f"SKILL.md missing in {skill_dir.name}"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_has_frontmatter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    lines = text.split("\n")
    assert lines[0].strip() == "---", f"{skill_dir.name}/SKILL.md does not start with ---"
    has_close = any(line.strip() == "---" for line in lines[1:])
    assert has_close, f"{skill_dir.name}/SKILL.md has no closing ---"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_frontmatter_has_name(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("name", "").strip(), f"{skill_dir.name}/SKILL.md missing non-empty 'name'"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_frontmatter_has_description(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("description", "").strip(), f"{skill_dir.name}/SKILL.md missing non-empty 'description'"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_frontmatter_has_group(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("group", "").strip(), f"{skill_dir.name}/SKILL.md missing non-empty 'group'"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_name_matches_dir(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    fm = _parse_frontmatter(text)
    assert fm.get("name") == skill_dir.name, (
        f"{skill_dir.name}/SKILL.md: 'name' field is '{fm.get('name')}', expected '{skill_dir.name}'"
    )
