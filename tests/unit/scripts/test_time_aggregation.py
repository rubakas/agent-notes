"""Tests for time aggregation in _claude_backend cost-report."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_notes.scripts import _claude_backend


# ── helpers ───────────────────────────────────────────────────────────────────

def _ts(offset_seconds: float = 0.0) -> str:
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


def _tool_use_result_msg(agent_type: str, duration_ms: int) -> dict:
    """Simulate a user message carrying toolUseResult metadata from a sub-agent invocation."""
    return {
        "type": "user",
        "toolUseResult": {
            "agentType": agent_type,
            "totalDurationMs": duration_ms,
        },
    }


def _string_tool_use_result_msg(stdout: str = "some bash output") -> dict:
    """Simulate a user message where toolUseResult is a raw string (Bash tool result)."""
    return {
        "type": "user",
        "toolUseResult": stdout,
    }


def _make_session(tmp_path: Path, subagents: list[dict],
                  lead_offsets: list[float] = None) -> tuple[str, str]:
    """
    Write a synthetic Claude Code session.

    subagents: list of dicts with keys:
      - label: str
      - offset: float (timestamp offset for the subagent's assistant message)
      - inp, outp: int
      - duration_ms: int (optional; written into parent transcript as toolUseResult)

    lead_offsets: list of timestamp offsets for lead assistant messages
                  (defaults to [0.0, 60.0] so lead_time_ms = 60 000)

    Returns (slug, session_uuid).
    """
    if lead_offsets is None:
        lead_offsets = [0.0, 60.0]

    session_uuid = str(uuid.uuid4())
    slug = str(tmp_path).replace("/", "-")
    proj_dir = tmp_path / ".claude" / "projects" / slug
    proj_dir.mkdir(parents=True)

    # Main transcript — lead assistant messages + toolUseResult entries
    main_lines = []
    for off in lead_offsets:
        main_lines.append(json.dumps(_assistant_msg(offset=off)))
    for sa in subagents:
        if "duration_ms" in sa:
            main_lines.append(json.dumps(_tool_use_result_msg(sa["label"], sa["duration_ms"])))

    main_jsonl = proj_dir / f"{session_uuid}.jsonl"
    main_jsonl.write_text("\n".join(main_lines) + "\n")

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

class TestTimeAggregation:
    def test_lead_time_from_assistant_ts_span(self, tmp_path, monkeypatch, capsys):
        """Lead time is computed as span between first and last lead assistant messages."""
        # lead has messages at t=0 and t=120 → 120 s → "2m"
        _make_session(tmp_path, subagents=[], lead_offsets=[0.0, 120.0])

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        _claude_backend.run()
        out = capsys.readouterr().out
        assert "2m" in out, f"Expected '2m' in output:\n{out}"

    def test_subagent_time_from_tool_use_result(self, tmp_path, monkeypatch, capsys):
        """Sub-agent time is taken from toolUseResult.totalDurationMs in parent transcript."""
        # coder duration = 170 000 ms = 170 s = "2m 50s"
        subagents = [{"label": "coder", "offset": 300, "duration_ms": 170_000}]
        _make_session(tmp_path, subagents=subagents, lead_offsets=[0.0])

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        _claude_backend.run()
        out = capsys.readouterr().out
        assert "2m 50s" in out, f"Expected '2m 50s' in output:\n{out}"

    def test_no_time_data_shows_na(self, tmp_path, monkeypatch, capsys):
        """When no duration data is available, time column shows n/a."""
        # Single lead message (no span) and no toolUseResult entries
        _make_session(tmp_path, subagents=[], lead_offsets=[0.0])

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        _claude_backend.run()
        out = capsys.readouterr().out
        assert "n/a" in out, f"Expected 'n/a' in output:\n{out}"

    def test_multiple_subagent_durations_summed(self, tmp_path, monkeypatch, capsys):
        """Multiple toolUseResult entries for same agent type are summed."""
        # Two coder invocations: 60s + 30s = 90s = "1m 30s"
        main_lines = [
            json.dumps(_assistant_msg(offset=0.0)),
            json.dumps(_tool_use_result_msg("coder", 60_000)),
            json.dumps(_tool_use_result_msg("coder", 30_000)),
        ]

        session_uuid = str(uuid.uuid4())
        slug = str(tmp_path).replace("/", "-")
        proj_dir = tmp_path / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        main_jsonl = proj_dir / f"{session_uuid}.jsonl"
        main_jsonl.write_text("\n".join(main_lines) + "\n")

        sa_dir = proj_dir / session_uuid / "subagents"
        sa_dir.mkdir(parents=True)
        sa_jsonl = sa_dir / "agent-0000.jsonl"
        sa_jsonl.write_text(json.dumps(_assistant_msg(offset=60.0)) + "\n")
        meta = sa_dir / "agent-0000.meta.json"
        meta.write_text(json.dumps({"agentType": "coder"}))

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        _claude_backend.run()
        out = capsys.readouterr().out
        assert "1m 30s" in out, f"Expected '1m 30s' in output:\n{out}"

    def test_string_tool_use_result_does_not_crash(self, tmp_path, monkeypatch, capsys):
        """String-typed toolUseResult (Bash tool output) must not crash and contributes 0ms."""
        # Mix a string toolUseResult with a valid dict one; only the dict should count.
        main_lines = [
            json.dumps(_assistant_msg(offset=0.0)),
            json.dumps(_string_tool_use_result_msg("raw bash stdout")),
            json.dumps(_tool_use_result_msg("coder", 30_000)),
        ]

        session_uuid = str(uuid.uuid4())
        slug = str(tmp_path).replace("/", "-")
        proj_dir = tmp_path / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        main_jsonl = proj_dir / f"{session_uuid}.jsonl"
        main_jsonl.write_text("\n".join(main_lines) + "\n")

        sa_dir = proj_dir / session_uuid / "subagents"
        sa_dir.mkdir(parents=True)
        sa_jsonl = sa_dir / "agent-0000.jsonl"
        sa_jsonl.write_text(json.dumps(_assistant_msg(offset=30.0)) + "\n")
        meta = sa_dir / "agent-0000.meta.json"
        meta.write_text(json.dumps({"agentType": "coder"}))

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        # Must not raise AttributeError
        _claude_backend.run()
        out = capsys.readouterr().out

        # The dict-typed result (30 000 ms = 30s) should still be reflected
        assert "30s" in out, f"Expected '30s' in output:\n{out}"

    def test_total_row_sums_all_durations(self, tmp_path, monkeypatch, capsys):
        """TOTAL row time = lead_time + sum of sub-agent durations."""
        # lead: 60s span, coder: 30s → total = 90s = "1m 30s"
        subagents = [{"label": "coder", "offset": 300, "duration_ms": 30_000}]
        _make_session(tmp_path, subagents=subagents, lead_offsets=[0.0, 60.0])

        monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("pathlib.Path.cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr("agent_notes.scripts._claude_backend._state_file",
                            lambda: tmp_path / "nonexistent-state.json")

        _claude_backend.run()
        out = capsys.readouterr().out
        # The TOTAL line should contain the summed duration
        lines = out.splitlines()
        total_line = next((l for l in lines if "TOTAL" in l), None)
        assert total_line is not None, "TOTAL row not found"
        assert "1m 30s" in total_line, f"Expected '1m 30s' in TOTAL row: {total_line}"
