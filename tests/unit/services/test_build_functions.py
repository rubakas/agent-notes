"""Tests for individual build command functions in isolation."""
import importlib
import json
import pytest
from pathlib import Path
from unittest.mock import patch

# Must use importlib because agent_notes.commands exports a `build` function
# at package level, shadowing the submodule when accessed via attribute lookup.
_build_mod = importlib.import_module("agent_notes.commands.build")



def test_copy_skills_copies_all_skill_dirs(tmp_path):
    """copy_skills() should copy every skill directory to dist/skills/."""
    skills_src = tmp_path / "skills"
    skill_a = skills_src / "alpha"
    skill_b = skills_src / "beta"
    skill_a.mkdir(parents=True)
    skill_b.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text("---\nname: alpha\n---\n")
    (skill_b / "SKILL.md").write_text("---\nname: beta\n---\n")

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    import agent_notes.config as config_mod

    def fake_find_skill_dirs():
        return sorted(d for d in skills_src.iterdir() if d.is_dir() and (d / "SKILL.md").exists())

    with patch.object(_build_mod, "DIST_DIR", dist_dir), \
         patch.object(config_mod, "find_skill_dirs", fake_find_skill_dirs):
        copied = _build_mod.copy_skills()

    assert len(copied) == 2
    names = {p.name for p in copied}
    assert "alpha" in names
    assert "beta" in names


def test_copy_global_files_returns_list_of_paths(tmp_path):
    """copy_global_files() should return a list of Path objects without error."""
    result = _build_mod.copy_global_files()
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, Path)
