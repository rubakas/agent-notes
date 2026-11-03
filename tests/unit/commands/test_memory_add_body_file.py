"""`agent-notes memory add --body-file` driven through the real CLI entry point."""
import io
import sys

import pytest

from agent_notes.cli import main


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Obsidian vault under tmp_path; never touches the real HOME."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    monkeypatch.setattr(
        "agent_notes.memory.commands._common._load_memory_config",
        lambda: ("obsidian", vault_dir),
    )
    monkeypatch.setattr(
        "agent_notes.memory.obsidian_backend.obsidian_regenerate_index",
        lambda vault: None,
    )
    monkeypatch.setattr("agent_notes.services.state_store.load_state", lambda *a, **k: None)
    return vault_dir


def _notes(vault_dir):
    return [p for p in vault_dir.rglob("*.md") if p.name != "Index.md"]


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["agent-notes", "memory", "add", *argv])
    main()


BODY = "First line\n\n## Section\n- item one\n- item two\n"


class TestMemoryAddBodyFile:
    def test_body_from_file_keeps_real_newlines(self, vault, tmp_path, monkeypatch):
        body_path = tmp_path / "body.md"
        body_path.write_text(BODY, encoding="utf-8")

        _run(monkeypatch, "File Note", "--body-file", str(body_path))

        notes = _notes(vault)
        assert len(notes) == 1
        content = notes[0].read_text()
        assert BODY in content
        assert "\\n" not in content

    def test_body_from_stdin_honours_type_and_agent(self, vault, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(BODY))

        _run(monkeypatch, "Stdin Note", "pattern", "lead", "--body-file", "-")

        notes = _notes(vault)
        assert len(notes) == 1
        content = notes[0].read_text()
        assert BODY in content
        assert "type: pattern" in content
        assert "pattern" in notes[0].relative_to(vault).parts[0].lower()

    def test_positional_body_conflicts_with_body_file(self, vault, tmp_path, monkeypatch, capsys):
        body_path = tmp_path / "body.md"
        body_path.write_text(BODY, encoding="utf-8")

        with pytest.raises(SystemExit) as exc:
            _run(monkeypatch, "Clash", "some text", "--body-file", str(body_path))

        assert exc.value.code == 1
        assert "--body-file" in capsys.readouterr().err
        assert _notes(vault) == []

    def test_missing_file_reports_path_and_writes_nothing(self, vault, tmp_path, monkeypatch, capsys):
        missing = tmp_path / "nope.md"

        with pytest.raises(SystemExit) as exc:
            _run(monkeypatch, "Missing", "--body-file", str(missing))

        assert exc.value.code == 1
        assert str(missing) in capsys.readouterr().err
        assert _notes(vault) == []

    def test_empty_path_is_an_unreadable_file_not_unset(self, vault, monkeypatch, capsys):
        with pytest.raises(SystemExit) as exc:
            _run(monkeypatch, "Empty", "--body-file", "")

        assert exc.value.code == 1
        assert "--body-file" in capsys.readouterr().err
        assert _notes(vault) == []
