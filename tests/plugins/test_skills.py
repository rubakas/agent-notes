"""Parametrized tests for every skill directory in data/skills/."""
import pytest
from pathlib import Path

from agent_notes.config import SKILLS_DIR
from agent_notes.memory.memory_backend import _REGISTRY, _REMOVED_BACKENDS


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


# Derived from the live backend registry, minus _REMOVED_BACKENDS, so that removing
# a backend automatically tightens this gate instead of leaving a dead name valid.
VALID_MEMORY_BACKENDS = set(_REGISTRY) - _REMOVED_BACKENDS


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_requires_memory_has_valid_backends(skill_dir):
    """If requires_memory is set, all values must be valid backend names."""
    text = (skill_dir / "SKILL.md").read_text()
    fm = _parse_frontmatter(text)
    requires = fm.get("requires_memory", "")
    if requires:
        backends = {b.strip() for b in requires.split(",")}
        invalid = backends - VALID_MEMORY_BACKENDS
        assert not invalid, (
            f"{skill_dir.name}/SKILL.md has invalid requires_memory backends: {invalid}"
        )


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_requires_memory_canonical_format(skill_dir):
    """If requires_memory is set, it must use canonical format: comma-separated with no spaces after commas."""
    text = (skill_dir / "SKILL.md").read_text()
    fm = _parse_frontmatter(text)
    requires = fm.get("requires_memory", "")
    if requires:
        tokens = requires.split(",")
        for token in tokens:
            assert token == token.strip(), (
                f"{skill_dir.name}/SKILL.md: requires_memory token '{token}' has leading/trailing whitespace; "
                f"use canonical form 'token1,token2' (no spaces after comma)"
            )


# Skills written for this project rather than vendored from upstream. Every
# directory in data/skills/ is either listed here or carries an entry in
# THIRD_PARTY_SKILLS.yaml; the manifest is provenance metadata that nothing
# else in the repo reads, so without this gate a skill can be added or an entry
# can go stale with no failure anywhere.
IN_HOUSE_SKILLS = frozenset({
    "chrome-test",
    "docker",
    "git",
    "ingest",
    "migrate-memory",
    "obsidian-memory",
    "rails",
    "refactoring-protocol",
    "rsi",
})

THIRD_PARTY_MANIFEST = Path(__file__).resolve().parents[2] / "THIRD_PARTY_SKILLS.yaml"


def _manifest_skill_names() -> set:
    import yaml
    manifest = yaml.safe_load(THIRD_PARTY_MANIFEST.read_text()) or {}
    return {entry["name"] for entry in manifest.get("skills", [])}


def test_third_party_manifest_exists():
    assert THIRD_PARTY_MANIFEST.is_file(), (
        f"{THIRD_PARTY_MANIFEST.name} is missing — vendored skills have no provenance record"
    )


def test_every_skill_has_a_provenance_decision():
    """Manifest entries plus in-house names must equal the directories on disk.

    Adding a skill fails this test until it is recorded as vendored (with its
    upstream path and local modifications) or declared in-house.
    """
    on_disk = {d.name for d in SKILL_DIRS}
    vendored = _manifest_skill_names()

    overlap = vendored & IN_HOUSE_SKILLS
    assert not overlap, (
        f"{sorted(overlap)} are claimed both as vendored and as in-house"
    )

    accounted = vendored | IN_HOUSE_SKILLS
    assert accounted == on_disk, (
        f"skills with no provenance decision: {sorted(on_disk - accounted)}; "
        f"declared but not on disk: {sorted(accounted - on_disk)}"
    )
