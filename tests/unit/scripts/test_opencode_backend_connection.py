"""Regression test: _opencode_backend.run() must not leak a sqlite3 connection.

Bug: `sqlite3.connect(DB).execute(SQL).fetchall()` opened a connection that was
never explicitly closed — the connection object was dropped without close().
Fix: use `with sqlite3.connect(DB) as conn:` so the connection is always closed.

The fail-first test injects a spy around sqlite3.connect and asserts close() is
called.  On the unfixed code, close() is never called explicitly, so only the GC
would clean it up — failing the assertion.
"""

import sqlite3
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_notes.scripts import _opencode_backend


def _make_db(tmp_path: Path) -> Path:
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
    now_ms = int(time.time() * 1000)
    session_id = "sess-001"
    conn.execute("INSERT INTO session VALUES (?, NULL, ?)", (session_id, now_ms))
    msg_data = json.dumps({
        "role": "assistant",
        "modelID": "claude-sonnet-4-5",
        "tokens": {"input": 100, "output": 100, "cache": {"read": 0}},
        "time": {"created": now_ms - 1000, "completed": now_ms},
        "agent": "lead",
    })
    conn.execute("INSERT INTO message VALUES (?, ?, ?)", ("msg-001", session_id, msg_data))
    conn.commit()
    conn.close()
    return db_path


class TestOpencodeBackendConnectionNotLeaked:
    def test_connection_is_explicitly_closed_after_run(self, tmp_path, capsys):
        """sqlite3 connection must be explicitly closed (not leaked) after run()."""
        db = _make_db(tmp_path)

        _original_connect = sqlite3.connect
        close_calls = []

        class _SpyConn:
            """Thin wrapper that records close() calls."""

            def __init__(self, path):
                self._real = _original_connect(path)

            def execute(self, sql):
                return self._real.execute(sql)

            def close(self):
                close_calls.append("close")
                self._real.close()

            # Context-manager support (used by `with sqlite3.connect(...) as conn:`)
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                close_calls.append("close")
                self._real.close()
                return False

        with patch("agent_notes.scripts._opencode_backend.sqlite3.connect",
                   side_effect=lambda path: _SpyConn(path)):
            with patch.object(_opencode_backend, "DB", db):
                rc = _opencode_backend.run()

        assert rc == 0
        assert len(close_calls) >= 1, (
            "sqlite3 connection was never explicitly closed — resource leak detected"
        )

    def test_run_returns_correct_rows(self, tmp_path, capsys):
        """run() must still return 0 and produce output after the connection-management fix."""
        db = _make_db(tmp_path)
        with patch.object(_opencode_backend, "DB", db):
            rc = _opencode_backend.run()
        assert rc == 0
        out = capsys.readouterr().out
        assert out.strip(), "Expected some output from run()"
