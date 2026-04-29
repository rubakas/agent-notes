"""Tests for session-id-based scoping in _claude_backend."""
import json
import uuid
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_notes.scripts import _claude_backend


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

        import agent_notes.scripts._claude_backend as backend

        backend.run()
        out = capsys.readouterr().out
        for label in ("coder", "reviewer", "test-writer", "devops"):
            assert label in out, f"Expected agent label '{label}' in output"

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

    def test_cost_report_header_contains_session_id(
        self, tmp_path, monkeypatch, capsys
    ):
        _, session_uuid = _make_session(tmp_path, [])
        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))

        import agent_notes.scripts._claude_backend as backend
        backend.run()
        out = capsys.readouterr().out

        session_line = next(
            (line for line in out.splitlines() if line.startswith("Session:")), None
        )
        assert session_line is not None, "Expected a 'Session:' header line"
        assert session_uuid in session_line

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

        import agent_notes.scripts._claude_backend as backend
        backend.run()
        out = capsys.readouterr().out

        # Both messages contribute: total input = 100 + 200 = 300
        # fmt_tokens formats 300 as "300" (< 1000)
        assert "300" in out, "Expected combined token count (300 input) in TOTAL row"
