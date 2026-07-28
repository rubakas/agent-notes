"""Regression tests: pricing lookup uses raw dash-form model IDs directly.

With normalization gone, get_price() matches provider-form IDs (e.g.
'claude-opus-4-8') against dash-separated anchored globs in pricing.yaml.
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
        opus_price = _pricing.get_price("claude-opus-4-8")
        legacy_price = _pricing.get_price("claude-opus-4-1")

        # Sanity: confirm we have distinct pricing tiers to differentiate
        assert opus_price["in"] < legacy_price["in"], (
            "Test precondition failed: expected Opus 4.8 cheaper than legacy Opus"
        )

        actual_price = _pricing.get_price("claude-opus-4-8")
        assert actual_price["in"] == opus_price["in"], (
            f"'claude-opus-4-8' priced at {actual_price['in']} instead of {opus_price['in']}"
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


class TestOpus5Pricing:
    """Regression tests for Opus pricing with raw dash-form IDs (no normalization)."""

    def test_opus5_uses_current_rate_not_legacy(self):
        """Regression: get_price('claude-opus-5')['in'] must be 5.0."""
        price = _pricing.get_price("claude-opus-5")
        assert price["in"] == 5.0, (
            f"claude-opus-5 priced at {price['in']}/M in — expected 5.0 (current rate), not 15.0 (legacy)"
        )

    def test_opus41_still_legacy(self):
        """Explicit legacy pin: claude-opus-4-1 must still resolve at $15/M."""
        price = _pricing.get_price("claude-opus-4-1")
        assert price["in"] == 15.0, (
            f"claude-opus-4-1 priced at {price['in']}/M in — expected 15.0 (legacy rate)"
        )

    def test_opus40_still_legacy(self):
        """Explicit legacy pin: claude-opus-4-0 must resolve at $15/M."""
        price = _pricing.get_price("claude-opus-4-0")
        assert price["in"] == 15.0, (
            f"claude-opus-4-0 priced at {price['in']}/M in — expected 15.0 (legacy rate)"
        )

    def test_bare_opus4_still_legacy(self):
        """Explicit legacy pin: bare 'claude-opus-4' must resolve at $15/M."""
        price = _pricing.get_price("claude-opus-4")
        assert price["in"] == 15.0, (
            f"claude-opus-4 priced at {price['in']}/M in — expected 15.0 (legacy rate)"
        )

    def test_dated_snapshot_ids_price_correctly(self):
        """Dated snapshot IDs match directly without normalization.

        Real message.model census (local transcripts, 2026-07-27):
          18,354  claude-sonnet-5
           9,799  claude-opus-4-8
           7,351  claude-sonnet-4-6
           7,319  claude-haiku-4-5-20251001   ← most common dated form
             498  claude-opus-5
             260  claude-fable-5
              14  <synthetic>

        These assertions are regression locks against removing a trailing '*' from a
        pricing glob, which would silently break dated forms.
        """
        from agent_notes.scripts._pricing import get_price

        # haiku dated — matches *haiku*
        assert get_price("claude-haiku-4-5-20251001")["in"] == 1.0, (
            "claude-haiku-4-5-20251001 priced incorrectly (expected 1.0/M in)"
        )

        # opus-4-5 dated — matches *opus-4-5-*
        assert get_price("claude-opus-4-5-20251101")["in"] == 5.0, (
            "claude-opus-4-5-20251101 priced incorrectly (expected 5.0/M in, not 15.0 legacy)"
        )

        # sonnet-4 dated — matches *sonnet*
        assert get_price("claude-sonnet-4-5-20250929")["in"] == 3.0, (
            "claude-sonnet-4-5-20250929 priced incorrectly (expected 3.0/M in)"
        )

        # opus-5 future dated — matches *opus-5-*
        assert get_price("claude-opus-5-20260401")["in"] == 5.0, (
            "claude-opus-5-20260401 priced incorrectly (expected 5.0/M in via *opus-5-* pin)"
        )

    def test_unknown_opus_warns_to_stderr_instead_of_silent_misprice(self, capsys):
        """An unknown future Opus (e.g. claude-opus-9) must emit a warning and NOT
        silently return the legacy rate — the *opus* catch-all has been removed."""
        _pricing.get_price("claude-opus-9")
        err = capsys.readouterr().err
        assert "no pricing entry" in err, (
            f"Expected 'no pricing entry' warning on stderr for unknown model, got: {err!r}"
        )


class TestOpus4ThirdBugRegression:
    """Regression tests for the claude-opus-4-10/4-11 mispricing bug.

    With the old dotted normalization, claude-opus-4-10 became claude-opus-4.10
    which matched *opus-4.1* (the legacy glob), mispricing at $15/M in.
    With dashed anchored globs, claude-opus-4-10 finds no match and warns instead.
    """

    def test_opus_4_10_does_not_price_at_legacy_rate(self, capsys):
        """claude-opus-4-10 must not match the legacy row — it should warn instead."""
        price = _pricing.get_price("claude-opus-4-10")
        err = capsys.readouterr().err
        assert "no pricing entry" in err, (
            f"Expected 'no pricing entry' warning for claude-opus-4-10, got: {err!r}"
        )
        assert price["in"] != 15.0, (
            "claude-opus-4-10 incorrectly priced at legacy $15/M rate"
        )

    def test_opus_4_11_does_not_price_at_legacy_rate(self, capsys):
        """claude-opus-4-11 must not match the legacy row — it should warn instead."""
        price = _pricing.get_price("claude-opus-4-11")
        err = capsys.readouterr().err
        assert "no pricing entry" in err, (
            f"Expected 'no pricing entry' warning for claude-opus-4-11, got: {err!r}"
        )
        assert price["in"] != 15.0, (
            "claude-opus-4-11 incorrectly priced at legacy $15/M rate"
        )

    def test_opus_4_1_still_legacy(self):
        """Real legacy model claude-opus-4-1 must still price at $15/M."""
        price = _pricing.get_price("claude-opus-4-1")
        assert price["in"] == 15.0, (
            f"claude-opus-4-1 priced at {price['in']}/M in — expected 15.0 (legacy rate)"
        )

    def test_opus_4_1_dated_still_legacy(self):
        """Dated legacy: claude-opus-4-1-20250805 must price at $15/M."""
        price = _pricing.get_price("claude-opus-4-1-20250805")
        assert price["in"] == 15.0, (
            f"claude-opus-4-1-20250805 priced at {price['in']}/M in — expected 15.0 (legacy rate)"
        )

    def test_dated_bare_opus4_still_legacy(self):
        """Dated bare Opus 4: claude-opus-4-20250514 must price at $15/M."""
        price = _pricing.get_price("claude-opus-4-20250514")
        assert price["in"] == 15.0, (
            f"claude-opus-4-20250514 priced at {price['in']}/M in — expected 15.0 (legacy rate)"
        )


class TestGithubCopilotAliasPricing:
    """GitHub Copilot aliases are dotted (github-copilot/claude-opus-4.8) while
    provider IDs are dashed (claude-opus-4-8). Both reach get_price via
    _opencode_backend (which passes the logged model string straight from
    opencode's DB), so both must price identically.
    """

    @pytest.mark.parametrize("model_id,expected_in", [
        ("github-copilot/claude-opus-4.8", 5.0),
        ("github-copilot/claude-opus-4.7", 5.0),
        ("github-copilot/claude-opus-4.6", 5.0),
        ("github-copilot/claude-opus-4.5", 5.0),
        ("github-copilot/claude-opus-4.1", 15.0),
        ("github-copilot/claude-sonnet-5", 3.0),
        ("github-copilot/claude-sonnet-4.6", 3.0),
        ("github-copilot/claude-sonnet-4.5", 3.0),
        ("github-copilot/claude-sonnet-4", 3.0),
        ("github-copilot/claude-haiku-4.5", 1.0),
        ("github-copilot/claude-fable-5", 10.0),
    ])
    def test_copilot_alias_prices_correctly(self, model_id, expected_in):
        price = _pricing.get_price(model_id)
        assert price["in"] == expected_in, (
            f"{model_id} priced at {price['in']}/M in — expected {expected_in}"
        )

    @pytest.mark.parametrize("version", ["4-8", "4-7", "4-6", "4-5"])
    def test_dashed_and_dotted_opus_agree(self, version):
        """Dashed provider form and dotted copilot alias must resolve to identical pricing."""
        dashed = _pricing.get_price(f"claude-opus-{version}")
        dotted = _pricing.get_price(f"github-copilot/claude-opus-{version.replace('-', '.')}")
        assert dashed == dotted, (
            f"claude-opus-{version} (dashed) and github-copilot/claude-opus-{version.replace('-', '.')} "
            f"(dotted) resolved to different prices: {dashed} vs {dotted}"
        )

    def test_opus_4_10_no_legacy_rate(self, capsys):
        """claude-opus-4-10 must warn (not price at legacy rate) — dotted globs must not widen scope."""
        price = _pricing.get_price("claude-opus-4-10")
        err = capsys.readouterr().err
        assert "no pricing entry" in err, (
            f"Expected 'no pricing entry' warning for claude-opus-4-10, got: {err!r}"
        )
        assert price["in"] != 15.0, "claude-opus-4-10 incorrectly priced at legacy $15/M rate"

    def test_opus_4_11_no_legacy_rate(self, capsys):
        """claude-opus-4-11 must warn (not price at legacy rate) — dotted globs must not widen scope."""
        price = _pricing.get_price("claude-opus-4-11")
        err = capsys.readouterr().err
        assert "no pricing entry" in err, (
            f"Expected 'no pricing entry' warning for claude-opus-4-11, got: {err!r}"
        )
        assert price["in"] != 15.0, "claude-opus-4-11 incorrectly priced at legacy $15/M rate"

    def test_opus_6_no_legacy_rate(self, capsys):
        """claude-opus-6 must warn and not price at any known rate — future model must be unmatched."""
        price = _pricing.get_price("claude-opus-6")
        err = capsys.readouterr().err
        assert "no pricing entry" in err, (
            f"Expected 'no pricing entry' warning for claude-opus-6, got: {err!r}"
        )
        assert price["in"] != 15.0, "claude-opus-6 incorrectly priced at legacy $15/M rate"


class TestRawDashedIdsNoNormalization:
    """Confirm these IDs price correctly with raw dashed form and no normalization."""

    @pytest.mark.parametrize("model_id,expected_in", [
        ("claude-opus-5", 5.0),
        ("claude-opus-5-20260401", 5.0),
        ("claude-opus-4-8", 5.0),
        ("claude-opus-4-5-20251101", 5.0),
        ("claude-haiku-4-5-20251001", 1.0),
        ("claude-sonnet-5", 3.0),
        ("claude-sonnet-4-5-20250929", 3.0),
        ("claude-fable-5", 10.0),
    ])
    def test_raw_dashed_id_prices_correctly(self, model_id, expected_in):
        price = _pricing.get_price(model_id)
        assert price["in"] == expected_in, (
            f"{model_id} priced at {price['in']}/M in — expected {expected_in}"
        )
