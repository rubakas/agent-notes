"""Schema test for the skill-eval prompt set (spec 009 Req 11, SC-013).

Static checks only: no model is called. See README.md for the live runner.
"""
from collections import Counter
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE.parent.parent / "agent_notes" / "data" / "skills"
PROMPTS_FILE = HERE / "prompts.yaml"

KEYS = {"skill", "category", "prompt", "expected_behaviour"}
CATEGORIES = {"should_trigger", "near_miss"}
MIN_TOTAL = 100
MIN_SHOULD_TRIGGER = 3
MIN_NEAR_MISS = 1


def load_entries(path=PROMPTS_FILE):
    return yaml.safe_load(path.read_text())


def skill_names():
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())


def schema_errors(entries, skills):
    """Return a list of human-readable problems; empty means the set is valid."""
    if not isinstance(entries, list):
        return ["prompts.yaml must be a YAML list"]
    errors = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry {i}: not a mapping")
            continue
        if set(entry) != KEYS:
            errors.append(f"entry {i}: keys {sorted(entry)} != {sorted(KEYS)}")
            continue
        for key in sorted(KEYS):
            value = entry[key]
            if not isinstance(value, str) or not value.strip():
                errors.append(f"entry {i}: {key} must be a non-empty string")
        if entry["category"] not in CATEGORIES:
            errors.append(f"entry {i}: category {entry['category']!r} not in {sorted(CATEGORIES)}")
        if entry["skill"] not in skills:
            errors.append(f"entry {i}: skill {entry['skill']!r} is not a directory under agent_notes/data/skills")
    if errors:
        return errors

    counts = Counter((e["skill"], e["category"]) for e in entries)
    for skill in skills:
        if counts[(skill, "should_trigger")] < MIN_SHOULD_TRIGGER:
            errors.append(f"{skill}: {counts[(skill, 'should_trigger')]} should_trigger, need >= {MIN_SHOULD_TRIGGER}")
        if counts[(skill, "near_miss")] < MIN_NEAR_MISS:
            errors.append(f"{skill}: {counts[(skill, 'near_miss')]} near_miss, need >= {MIN_NEAR_MISS}")
    if len(entries) < MIN_TOTAL:
        errors.append(f"{len(entries)} entries, need >= {MIN_TOTAL}")
    return errors


def test_prompts_yaml_is_valid_and_covers_every_skill():
    assert schema_errors(load_entries(), skill_names()) == []


def test_prompts_yaml_parses():
    assert isinstance(load_entries(), list)


def test_skill_directories_exist():
    assert len(skill_names()) >= 25


def test_mutation_dropping_a_skill_is_detected():
    entries = [e for e in load_entries() if e["skill"] != "git"]
    errors = schema_errors(entries, skill_names())
    assert any(e.startswith("git: 0 should_trigger") for e in errors)
    assert any(e.startswith("git: 0 near_miss") for e in errors)


def test_mutation_unknown_skill_is_detected():
    entries = load_entries() + [
        {"skill": "no-such-skill", "category": "near_miss", "prompt": "p", "expected_behaviour": "b"},
    ]
    assert any("no-such-skill" in e for e in schema_errors(entries, skill_names()))


@pytest.mark.parametrize("bad", [
    {"skill": "git", "category": "near_miss", "prompt": "p"},
    {"skill": "git", "category": "near_miss", "prompt": "p", "expected_behaviour": "b", "extra": "x"},
    {"skill": "git", "category": "near_miss", "prompt": "  ", "expected_behaviour": "b"},
    {"skill": "git", "category": "maybe", "prompt": "p", "expected_behaviour": "b"},
    {"skill": "git", "category": "near_miss", "prompt": 3, "expected_behaviour": "b"},
    "just a string",
])
def test_mutation_malformed_entry_is_detected(bad):
    assert schema_errors(load_entries() + [bad], skill_names())


def test_mutation_non_list_and_short_set_are_detected():
    assert schema_errors({"skill": "git"}, skill_names())
    assert any("need >= 100" in e for e in schema_errors(load_entries()[:99], skill_names()))
