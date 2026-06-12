"""Regression test: OpenCode backend normalizes dash-form model IDs before pricing lookup.

Without normalization, `claude-opus-4-8` fails the `*opus-4.8*` fnmatch glob and
falls through to the legacy `*opus*` catch-all ($15/M in instead of $5/M in).
"""
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from agent_notes.scripts import _pricing


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_opencode_db(tmp_path: Path, model: str, inp: int = 1_000_000, outp: int = 1_000_000) -> Path:
    """Build a minimal OpenCode SQLite DB with one session and one assistant message."""
    db_path = tmp_path / "opencode.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            parent_id TEXT,
            time_created INTEGER
        );
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            data TEXT
        );
    """)

    import json, time
    now_ms = int(time.time() * 1000)
    session_id = "sess-001"
    conn.execute(
        "INSERT INTO session VALUES (?, NULL, ?)",
        (session_id, now_ms),
    )
    # assistant message with the raw dash-form model ID
    msg_data = json.dumps({
        "role": "assistant",
        "modelID": model,
        "tokens": {"input": inp, "output": outp, "cache": {"read": 0}},
        "time": {"created": now_ms - 1000, "completed": now_ms},
        "agent": "lead",
    })
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        ("msg-001", session_id, msg_data),
    )
    conn.commit()
    conn.close()
    return db_path


# ── tests ─────────────────────────────────────────────────────────────────────

class TestOpencodeBackendNormalizesModel:
    def test_opus_dash_form_uses_opus_rate_not_legacy(self, tmp_path):
        """claude-opus-4-8 (dash form) must resolve to the $5/M Opus rate, not $15/M legacy."""
        opus_price = _pricing.get_price("claude-opus-4.8")
        legacy_price = _pricing.get_price("claude-opus-4.1")

        # Sanity: confirm we have distinct pricing tiers to differentiate
        assert opus_price["in"] < legacy_price["in"], (
            "Test precondition failed: expected Opus 4.8 cheaper than legacy Opus"
        )

        # Normalize as the backend should
        normalized = _pricing.normalize_model("claude-opus-4-8")
        assert normalized == "claude-opus-4.8"

        actual_price = _pricing.get_price(normalized)
        assert actual_price["in"] == opus_price["in"], (
            f"Normalized 'claude-opus-4-8' priced at {actual_price['in']} instead of {opus_price['in']}"
        )

    def test_opencode_run_uses_normalized_model(self, tmp_path, capsys):
        """Integration: _opencode_backend.run() prices opus-4-8 at the Opus rate end-to-end."""
        from agent_notes.scripts import _opencode_backend

        db = _make_opencode_db(tmp_path, model="claude-opus-4-8", inp=1_000_000, outp=0)

        with patch.object(_opencode_backend, "DB", db):
            rc = _opencode_backend.run()

        assert rc == 0
        out = capsys.readouterr().out

        # At 1M input tokens:
        #   Opus rate  ($5/M)  → $5.00
        #   Legacy rate ($15/M) → $15.00
        # The output must contain the Opus cost, not the legacy cost.
        assert "$5.00" in out or "5.00" in out, (
            f"Expected ~$5.00 (Opus rate) in output, got:\n{out}"
        )
        assert "$15.00" not in out and "15.00" not in out.replace("$5.00", ""), (
            f"Legacy rate ($15.00) appeared in output — normalization not applied:\n{out}"
        )
