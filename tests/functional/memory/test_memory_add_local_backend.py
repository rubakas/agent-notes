"""Regression test: memory add on local backend exits non-zero and prints to stderr.

Previously the command printed guidance to stdout and returned silently (exit 0),
causing callers to believe the note was saved when nothing was written.
"""
import pytest


class TestMemoryAddLocalBackendExitsNonZero:
    def test_local_backend_add_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        """memory add on local backend must exit non-zero — not silently succeed."""
        mem_dir = tmp_path / "memory"

        import agent_notes.commands.memory as mem_mod
        monkeypatch.setattr(mem_mod._common, "_load_memory_config", lambda: ("local", mem_dir))

        from agent_notes.commands.memory import memory
        with pytest.raises(SystemExit) as exc_info:
            memory(action="add", name="My Note", extra=["Body text", "context", "lead"])

        assert exc_info.value.code != 0, (
            "memory add on local backend must exit non-zero so callers detect the failure"
        )

    def test_local_backend_add_prints_guidance_to_stderr(self, tmp_path, monkeypatch, capsys):
        """Guidance message must go to stderr, not stdout, so pipelines can separate it."""
        mem_dir = tmp_path / "memory"

        import agent_notes.commands.memory as mem_mod
        monkeypatch.setattr(mem_mod._common, "_load_memory_config", lambda: ("local", mem_dir))

        from agent_notes.commands.memory import memory
        with pytest.raises(SystemExit):
            memory(action="add", name="My Note", extra=["Body text", "context", "lead"])

        captured = capsys.readouterr()
        assert captured.out == "", f"Expected no stdout output, got: {captured.out!r}"
        assert "local storage" in captured.err.lower() or "directly" in captured.err.lower(), (
            f"Expected guidance in stderr, got: {captured.err!r}"
        )

    def test_local_backend_add_writes_nothing(self, tmp_path, monkeypatch):
        """No file should be created in MEMORY_DIR when local backend is used."""
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()

        import agent_notes.commands.memory as mem_mod
        monkeypatch.setattr(mem_mod._common, "_load_memory_config", lambda: ("local", mem_dir))

        from agent_notes.commands.memory import memory
        with pytest.raises(SystemExit):
            memory(action="add", name="My Note", extra=["Body text", "context", "lead"])

        written = list(mem_dir.rglob("*"))
        assert written == [], f"Expected no files written, found: {written}"
