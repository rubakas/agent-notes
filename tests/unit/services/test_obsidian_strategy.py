"""Tests for M2: strategy-aware placement in the obsidian backend.

(a) per-project → new note lands in vault/<project>/<category>/
(b) single-brain → new note lands in vault/<category>/ (flat root, unchanged)
(c) note pre-existing in flat root is still returned by list after switching to per-project
    (nothing moved, nothing hidden)
"""

import pytest
from pathlib import Path

from agent_notes.memory.obsidian_backend import (
    obsidian_write_note,
    obsidian_list_notes,
    obsidian_regenerate_index,
)


class TestWritePlacementPerProject:
    """(a) per-project strategy: new note lands under vault/<project>/<category>/."""

    def test_pattern_note_lands_under_project_subfolder(self, tmp_path, monkeypatch):
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "myproject")

        path = obsidian_write_note(
            tmp_path,
            title="Test",
            body="body",
            note_type="pattern",
            strategy="per-project",
        )

        # Should be vault/myproject/Patterns/<filename>
        assert path.parent.name == "Patterns"
        assert path.parent.parent.name == "myproject"
        assert path.parent.parent.parent == tmp_path

    def test_decision_note_lands_under_project_subfolder(self, tmp_path, monkeypatch):
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "acme")

        path = obsidian_write_note(
            tmp_path,
            title="Arch decision",
            body="body",
            note_type="decision",
            strategy="per-project",
        )

        assert path.parent.name == "Decisions"
        assert path.parent.parent.name == "acme"

    def test_session_note_lands_under_project_subfolder(self, tmp_path, monkeypatch):
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "alpha")
        # Ensure no ambient session_id so the fallback slug path is exercised
        monkeypatch.setattr(mb, "_current_session_id", lambda: None)

        path = obsidian_write_note(
            tmp_path,
            title="My session",
            body="body",
            note_type="session",
            strategy="per-project",
        )

        assert path.parent.name == "Sessions"
        assert path.parent.parent.name == "alpha"

    def test_per_project_note_not_in_flat_root(self, tmp_path, monkeypatch):
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "proj")

        path = obsidian_write_note(
            tmp_path,
            title="Note",
            body="body",
            note_type="context",
            strategy="per-project",
        )

        # The file must NOT be directly under vault/Context/
        flat_context = tmp_path / "Context"
        assert path not in flat_context.glob("*.md") if flat_context.exists() else True


class TestWritePlacementSingleBrain:
    """(b) single-brain strategy: note lands in vault/<category>/ (unchanged behavior)."""

    def test_pattern_note_in_flat_root(self, tmp_path):
        path = obsidian_write_note(
            tmp_path,
            title="Flat note",
            body="body",
            note_type="pattern",
            strategy="single-brain",
        )

        # vault/Patterns/<filename>
        assert path.parent.name == "Patterns"
        assert path.parent.parent == tmp_path

    def test_default_strategy_is_single_brain(self, tmp_path):
        """Calling without strategy= uses single-brain (flat root)."""
        path = obsidian_write_note(
            tmp_path,
            title="Default strategy note",
            body="body",
            note_type="decision",
        )

        assert path.parent.name == "Decisions"
        assert path.parent.parent == tmp_path

    def test_session_note_in_flat_root(self, tmp_path, monkeypatch):
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_session_id", lambda: None)

        path = obsidian_write_note(
            tmp_path,
            title="Flat session",
            body="body",
            note_type="session",
            strategy="single-brain",
        )

        assert path.parent.name == "Sessions"
        assert path.parent.parent == tmp_path


class TestReadAcrossLayouts:
    """(c) list/recall finds notes written under EITHER strategy — nothing hidden."""

    def test_flat_root_note_visible_after_per_project_strategy(self, tmp_path):
        """A note written in flat root (single-brain) is still returned by
        obsidian_list_notes even when called from a per-project context."""
        # Write a note using single-brain (flat root)
        obsidian_write_note(
            tmp_path,
            title="Old flat note",
            body="body",
            note_type="pattern",
            strategy="single-brain",
        )

        # Now list — simulates having switched to per-project later
        notes = obsidian_list_notes(tmp_path)
        paths = [n["path"] for n in notes]
        # The flat-root note must appear
        assert any("Patterns" in p and "old-flat-note" in p for p in paths), (
            f"Flat-root note not found after strategy change: {paths}"
        )

    def test_per_project_note_visible_to_list(self, tmp_path, monkeypatch):
        """A note written with per-project is returned by obsidian_list_notes."""
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "proj")

        obsidian_write_note(
            tmp_path,
            title="Per project note",
            body="body",
            note_type="decision",
            strategy="per-project",
        )

        notes = obsidian_list_notes(tmp_path)
        paths = [n["path"] for n in notes]
        assert any("Decision" in p and "per-project-note" in p for p in paths), (
            f"Per-project note not found by list: {paths}"
        )

    def test_both_layouts_visible_simultaneously(self, tmp_path, monkeypatch):
        """Notes from both strategies are visible at the same time."""
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "beta")

        # Write one in flat root
        obsidian_write_note(
            tmp_path,
            title="Flat",
            body="body",
            note_type="pattern",
            strategy="single-brain",
        )
        # Write one in per-project
        obsidian_write_note(
            tmp_path,
            title="Per project",
            body="body",
            note_type="pattern",
            strategy="per-project",
        )

        notes = obsidian_list_notes(tmp_path)
        assert len(notes) >= 2, f"Expected at least 2 notes, got {len(notes)}: {notes}"

    def test_index_includes_per_project_notes(self, tmp_path, monkeypatch):
        """obsidian_regenerate_index includes notes from per-project subfolders."""
        import agent_notes.memory.obsidian_backend as mb
        monkeypatch.setattr(mb, "_current_project_name", lambda: "gamma")
        monkeypatch.setattr(mb, "_current_session_id", lambda: None)

        obsidian_write_note(
            tmp_path,
            title="Per project decision",
            body="body",
            note_type="decision",
            strategy="per-project",
        )

        index = (tmp_path / "Index.md").read_text()
        assert "per-project-decision" in index, (
            f"Per-project note not in index:\n{index}"
        )
