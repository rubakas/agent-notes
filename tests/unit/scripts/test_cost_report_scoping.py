"""Tests for session-id-based scoping in _claude_backend."""
import json
import sys
import uuid
import io
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_notes.scripts import _claude_backend
from agent_notes.scripts import cost_report


# ── fixture builder ───────────────────────────────────────────────────────────

def _ts(offset_seconds: float = 0.0) -> str:
    """Return an ISO Z timestamp relative to a fixed base time."""
    base = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)
    dt = datetime.fromtimestamp(base.timestamp() + offset_seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _assistant_msg(model: str = "claude-sonnet-4-5", inp: int = 100, outp: int = 50,
                   offset: float = 0.0) -> dict:
    return {
        "type": "message",
        "timestamp": _ts(offset),
        "message": {
            "role": "assistant",
            "model": model,
            "usage": {"input_tokens": inp, "output_tokens": outp, "cache_read_input_tokens": 0},
        },
    }


def _make_session(tmp_path: Path, subagents: list[dict]) -> tuple[str, str]:
    """Write a synthetic Claude Code session.

    subagents: list of dicts with keys: label, offset (float), inp, outp.

    Returns (slug, session_uuid).
    """
    session_uuid = str(uuid.uuid4())
    slug = str(tmp_path).replace("/", "-")
    proj_dir = tmp_path / ".claude" / "projects" / slug
    proj_dir.mkdir(parents=True)

    # Main transcript — one assistant message at t=0
    main_jsonl = proj_dir / f"{session_uuid}.jsonl"
    main_jsonl.write_text(json.dumps(_assistant_msg(offset=0.0)) + "\n")

    # Subagents
    sa_dir = proj_dir / session_uuid / "subagents"
    sa_dir.mkdir(parents=True)
    for i, sa in enumerate(subagents):
        sa_id = f"agent-{i:04d}"
        sa_jsonl = sa_dir / f"{sa_id}.jsonl"
        sa_jsonl.write_text(
            json.dumps(_assistant_msg(
                inp=sa.get("inp", 100),
                outp=sa.get("outp", 50),
                offset=sa.get("offset", float(i * 300)),
            )) + "\n"
        )
        meta = sa_dir / f"{sa_id}.meta.json"
        meta.write_text(json.dumps({"agentType": sa["label"]}))

    return slug, session_uuid


# ── tests ─────────────────────────────────────────────────────────────────────

class TestCostReportScoping:
    def test_cost_report_includes_all_subagents_for_session(
        self, tmp_path, monkeypatch, capsys
    ):
        subagents = [
            {"label": "coder", "offset": 300},
            {"label": "reviewer", "offset": 600},
            {"label": "test-writer", "offset": 900},
            {"label": "devops", "offset": 1200},
        ]
        slug, _ = _make_session(tmp_path, subagents)
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        import agent_notes.scripts._claude_backend as backend

        backend.run()
        out = capsys.readouterr().out
        for label in ("coder", "reviewer", "test-writer", "devops"):
            assert label in out, f"Expected agent label '{label}' in output"
        assert "Configured:" not in out

    def test_cost_report_since_flag_filters_by_timestamp(
        self, tmp_path, monkeypatch, capsys
    ):
        subagents = [
            {"label": "coder", "offset": 300, "inp": 111},
            {"label": "reviewer", "offset": 600, "inp": 222},
            {"label": "test-writer", "offset": 900, "inp": 333},
            {"label": "devops", "offset": 1200, "inp": 444},
        ]
        _make_session(tmp_path, subagents)

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        # since = just after the 3rd subagent's message (offset=900 => t+900s)
        base_ts = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        since = base_ts + 950.0  # after offset=900, before offset=1200

        import agent_notes.scripts._claude_backend as backend
        backend.run(since=since)
        out = capsys.readouterr().out

        # Only devops (offset=1200) should appear; coder/reviewer/test-writer should not
        assert "devops" in out
        assert "coder" not in out
        assert "reviewer" not in out
        assert "test-writer" not in out
        assert "Configured:" not in out

    def test_cost_report_header_contains_session_id(
        self, tmp_path, monkeypatch, capsys
    ):
        _, session_uuid = _make_session(tmp_path, [])
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        import agent_notes.scripts._claude_backend as backend
        backend.run()
        out = capsys.readouterr().out

        session_line = next(
            (line for line in out.splitlines() if line.startswith("Session:")), None
        )
        assert session_line is not None, "Expected a 'Session:' header line"
        assert session_uuid in session_line
        assert "Configured:" not in out

    def test_cost_report_no_15min_gap_logic(
        self, tmp_path, monkeypatch, capsys
    ):
        """Both messages (30-min gap apart) must appear in TOTAL — no implicit session-start cutoff."""
        session_uuid = str(uuid.uuid4())
        slug = str(tmp_path).replace("/", "-")
        proj_dir = tmp_path / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)

        # Two assistant messages: t=0 and t=1800 (30-min gap)
        main_jsonl = proj_dir / f"{session_uuid}.jsonl"
        lines = [
            json.dumps(_assistant_msg(inp=100, outp=50, offset=0.0)),
            json.dumps(_assistant_msg(inp=200, outp=100, offset=1800.0)),
        ]
        main_jsonl.write_text("\n".join(lines) + "\n")

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        import agent_notes.scripts._claude_backend as backend
        backend.run()
        out = capsys.readouterr().out

        # Both messages contribute: total input = 100 + 200 = 300
        # fmt_tokens formats 300 as "300" (< 1000)
        assert "300" in out, "Expected combined token count (300 input) in TOTAL row"
        assert "Configured:" not in out


class TestLoadConfiguredModels:
    def test_returns_role_models_when_state_json_exists(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "global": {
                "clis": {
                    "claude": {
                        "role_models": {
                            "lead": "claude-opus-4-7",
                            "coder": "claude-sonnet-4-6",
                        }
                    }
                }
            }
        }))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)

        result = _claude_backend._load_configured_models()

        assert result == {"lead": "claude-opus-4-7", "coder": "claude-sonnet-4-6"}

    def test_returns_empty_dict_when_state_json_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent.json")

        result = _claude_backend._load_configured_models()

        assert result == {}

    def test_returns_empty_dict_when_role_models_key_absent(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"global": {}}))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)

        result = _claude_backend._load_configured_models()

        assert result == {}

    def test_returns_local_role_models_when_global_is_none(self, tmp_path, monkeypatch):
        """Regression: global uninstalled leaves data["global"] as None; local install must be used."""
        state_file = tmp_path / "state.json"
        cwd = str(tmp_path)
        state_file.write_text(json.dumps({
            "global": None,
            "local": {
                cwd: {
                    "clis": {
                        "claude": {
                            "role_models": {
                                "lead": "claude-opus-4-7",
                                "coder": "claude-sonnet-4-6",
                            }
                        }
                    }
                }
            }
        }))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))

        result = _claude_backend._load_configured_models()

        assert result == {"lead": "claude-opus-4-7", "coder": "claude-sonnet-4-6"}

    def test_returns_empty_dict_when_both_global_and_local_absent(self, tmp_path, monkeypatch):
        """When global is None and local has no entry for cwd, return empty dict."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"global": None, "local": {}}))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))

        result = _claude_backend._load_configured_models()

        assert result == {}

    def test_returns_global_role_models_when_global_is_present(self, tmp_path, monkeypatch):
        """Regression guard: global install still takes priority when present."""
        state_file = tmp_path / "state.json"
        cwd = str(tmp_path)
        state_file.write_text(json.dumps({
            "global": {
                "clis": {
                    "claude": {
                        "role_models": {"lead": "claude-opus-4-7"}
                    }
                }
            },
            "local": {
                cwd: {
                    "clis": {
                        "claude": {
                            "role_models": {"lead": "claude-sonnet-4-6"}
                        }
                    }
                }
            }
        }))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))

        result = _claude_backend._load_configured_models()

        assert result == {"lead": "claude-opus-4-7"}


class TestConfiguredHeaderLine:
    def _write_state(self, state_file: Path, role_models: dict) -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({
            "global": {"clis": {"claude": {"role_models": role_models}}}
        }))

    def test_configured_line_appears_when_role_models_non_empty(
        self, tmp_path, monkeypatch, capsys
    ):
        state_file = tmp_path / "state.json"
        _make_session(tmp_path, [])
        self._write_state(state_file, {"lead": "claude-opus-4-7", "coder": "claude-sonnet-4-6"})
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)

        _claude_backend.run()
        out = capsys.readouterr().out

        configured_line = next(
            (line for line in out.splitlines() if line.startswith("Configured:")), None
        )
        assert configured_line is not None, "Expected a 'Configured:' header line"
        assert "coder=claude-sonnet-4-6" in configured_line
        assert "lead=claude-opus-4-7" in configured_line

    def test_configured_line_sorted_alphabetically(
        self, tmp_path, monkeypatch, capsys
    ):
        state_file = tmp_path / "state.json"
        _make_session(tmp_path, [])
        self._write_state(state_file, {
            "reviewer": "claude-sonnet-4-6",
            "coder": "claude-sonnet-4-6",
            "lead": "claude-opus-4-7",
        })
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)

        _claude_backend.run()
        out = capsys.readouterr().out

        configured_line = next(
            (line for line in out.splitlines() if line.startswith("Configured:")), None
        )
        assert configured_line is not None
        # Roles should appear in alphabetical order: coder, lead, reviewer
        coder_pos = configured_line.index("coder")
        lead_pos = configured_line.index("lead")
        reviewer_pos = configured_line.index("reviewer")
        assert coder_pos < lead_pos < reviewer_pos

    def test_configured_line_absent_when_role_models_empty(
        self, tmp_path, monkeypatch, capsys
    ):
        state_file = tmp_path / "state.json"
        _make_session(tmp_path, [])
        self._write_state(state_file, {})
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file", lambda: state_file)

        _claude_backend.run()
        out = capsys.readouterr().out

        assert "Configured:" not in out

    def test_configured_line_absent_when_state_json_missing(
        self, tmp_path, monkeypatch, capsys
    ):
        _make_session(tmp_path, [])
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        _claude_backend.run()
        out = capsys.readouterr().out

        assert "Configured:" not in out


class TestEnvVarSessionAutoPass:
    """Tests that cost_report.main() auto-populates session_id from CLAUDE_CODE_SESSION_ID."""

    def test_session_id_from_env_var(self, monkeypatch):
        """When CLAUDECODE=1 and CLAUDE_CODE_SESSION_ID=abc-123, run is called with session_id='abc-123'."""
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc-123")
        monkeypatch.delenv("OPENCODE", raising=False)
        monkeypatch.delenv("OPENCODE_SESSION_ID", raising=False)
        monkeypatch.setattr(sys, "argv", ["cost-report"])

        calls = []

        def fake_run(since=None, session_id=None):
            calls.append({"since": since, "session_id": session_id})
            return 0

        monkeypatch.setattr("agent_notes.scripts._claude_backend.run", fake_run)

        with patch(
            "agent_notes.services.user_config.load_user_config",
            return_value={"cost_report_enabled": True},
        ):
            cost_report.main()

        assert len(calls) == 1
        assert calls[0]["session_id"] == "abc-123"

    def test_explicit_session_overrides_env_var(self, monkeypatch):
        """Explicit --session flag wins over CLAUDE_CODE_SESSION_ID."""
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc-123")
        monkeypatch.delenv("OPENCODE", raising=False)
        monkeypatch.delenv("OPENCODE_SESSION_ID", raising=False)
        monkeypatch.setattr(sys, "argv", ["cost-report", "--session", "explicit-456"])

        calls = []

        def fake_run(since=None, session_id=None):
            calls.append({"since": since, "session_id": session_id})
            return 0

        monkeypatch.setattr("agent_notes.scripts._claude_backend.run", fake_run)

        with patch(
            "agent_notes.services.user_config.load_user_config",
            return_value={"cost_report_enabled": True},
        ):
            cost_report.main()

        assert len(calls) == 1
        assert calls[0]["session_id"] == "explicit-456"


class TestFindTranscriptDir:
    """Tests for _find_transcript_dir fallback search."""

    def test_find_transcript_dir_found(self, tmp_path, monkeypatch):
        """Returns the correct project directory when session JSONL exists."""
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))

        session_id = "my-session-abc"
        proj_dir = tmp_path / ".claude" / "projects" / "some-slug"
        proj_dir.mkdir(parents=True)
        (proj_dir / f"{session_id}.jsonl").write_text("{}\n")

        result = _claude_backend._find_transcript_dir(session_id)

        assert result == proj_dir

    def test_find_transcript_dir_not_found(self, tmp_path, monkeypatch):
        """Returns None when the session JSONL does not exist in any project dir."""
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))

        proj_dir = tmp_path / ".claude" / "projects" / "some-slug"
        proj_dir.mkdir(parents=True)
        (proj_dir / "other-session.jsonl").write_text("{}\n")

        result = _claude_backend._find_transcript_dir("nonexistent-session-id")

        assert result is None

    def test_find_transcript_dir_no_projects_dir(self, tmp_path, monkeypatch):
        """Returns None gracefully when ~/.claude/projects/ doesn't exist at all."""
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))

        # No .claude/projects directory created
        result = _claude_backend._find_transcript_dir("any-session-id")

        assert result is None


class TestRunFallbackSearch:
    """Tests that run() uses .resolve() and falls back to _find_transcript_dir."""

    def test_run_falls_back_to_search(self, tmp_path, monkeypatch, capsys):
        """When slug-based dir doesn't exist, run() finds transcript via _find_transcript_dir."""
        session_id = str(uuid.uuid4())

        # Create a project dir with a slug that will NOT match cwd's slug
        real_proj_dir = tmp_path / ".claude" / "projects" / "some-other-project-slug"
        real_proj_dir.mkdir(parents=True)
        jsonl = real_proj_dir / f"{session_id}.jsonl"
        jsonl.write_text(json.dumps(_assistant_msg()) + "\n")

        # Point home at tmp_path so ~/.claude resolves there
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        # cwd resolves to a path whose slug will NOT match "some-other-project-slug"
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path / "completely-different"))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        result = _claude_backend.run(session_id=session_id)
        out = capsys.readouterr().out

        assert "No Claude Code transcript found" not in out
        assert session_id in out

    def test_run_with_resolve(self, tmp_path, monkeypatch, capsys):
        """run() uses .resolve() on cwd — a symlinked path resolves to real path's slug."""
        session_id = str(uuid.uuid4())

        # The real resolved path
        real_dir = tmp_path / "real"
        real_dir.mkdir()

        # Slug is derived from the resolved path
        resolved_slug = str(real_dir).replace("/", "-")
        proj_dir = tmp_path / ".claude" / "projects" / resolved_slug
        proj_dir.mkdir(parents=True)
        jsonl = proj_dir / f"{session_id}.jsonl"
        jsonl.write_text(json.dumps(_assistant_msg()) + "\n")

        # cwd() returns a mock whose .resolve() returns real_dir
        class FakePath:
            def __str__(self):
                return str(real_dir / "symlink-name")  # pre-resolve path

            def resolve(self):
                return real_dir  # post-resolve path

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: FakePath()))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        result = _claude_backend.run(session_id=session_id)
        out = capsys.readouterr().out

        assert "No Claude Code transcript found" not in out
        assert session_id in out
