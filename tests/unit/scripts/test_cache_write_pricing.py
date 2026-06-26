"""Tests for G1 — cache write cost accuracy.

Covers:
- pricing.yaml has cache_read, cache_write_5m, cache_write_1h per model
- calculate_cost and baseline_cost price each bucket separately
- _claude_backend collects 5m/1h split from cache_creation nested object
- _claude_backend falls back to flat cache_creation_input_tokens as 5m writes
- transcripts with no cache fields at all compute without error (backward compat)
- end-to-end dollar amounts match hand-calculated values
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_notes.scripts import _pricing
from agent_notes.scripts import _claude_backend


# ── pricing unit tests ────────────────────────────────────────────────────────

class TestPricingYamlStructure:
    def test_all_anthropic_models_have_cache_read(self):
        data = _pricing._load()
        for provider in data["providers"]:
            if provider["name"] != "Anthropic":
                continue
            for model in provider["models"]:
                p = model["price"]
                assert "cache_read" in p, f"{model['name']} missing cache_read"

    def test_all_anthropic_models_have_cache_write_5m(self):
        data = _pricing._load()
        for provider in data["providers"]:
            if provider["name"] != "Anthropic":
                continue
            for model in provider["models"]:
                p = model["price"]
                assert "cache_write_5m" in p, f"{model['name']} missing cache_write_5m"

    def test_all_anthropic_models_have_cache_write_1h(self):
        data = _pricing._load()
        for provider in data["providers"]:
            if provider["name"] != "Anthropic":
                continue
            for model in provider["models"]:
                p = model["price"]
                assert "cache_write_1h" in p, f"{model['name']} missing cache_write_1h"

    def test_opus_cache_rates(self):
        p = _pricing.get_price("claude-opus-4.8")
        assert p["cache_read"] == 0.50
        assert p["cache_write_5m"] == 6.25
        assert p["cache_write_1h"] == 10.00

    def test_sonnet_cache_rates(self):
        p = _pricing.get_price("claude-sonnet-4.6")
        assert p["cache_read"] == 0.30
        assert p["cache_write_5m"] == 3.75
        assert p["cache_write_1h"] == 6.00

    def test_haiku_cache_rates(self):
        p = _pricing.get_price("claude-haiku-4.5")
        assert p["cache_read"] == 0.10
        assert p["cache_write_5m"] == 1.25
        assert p["cache_write_1h"] == 2.00

    def test_baseline_has_cache_fields(self):
        data = _pricing._load()
        p = data["baseline"]["price"]
        assert "cache_read" in p
        assert "cache_write_5m" in p
        assert "cache_write_1h" in p


class TestCalculateCostHandCalculated:
    """Verify calculate_cost matches hand calculations.

    Opus 4.8 rates: in=$5, out=$25, cache_read=$0.50, write_5m=$6.25, write_1h=$10.00
    (all per million tokens)

    Example: 1M read + 2M write_5m + 0.5M write_1h tokens on Opus, 0 in/out
      = 1_000_000 * 0.50 + 2_000_000 * 6.25 + 500_000 * 10.00
      = 0.50 + 12.50 + 5.00
      = $18.00
    """

    def test_opus_cache_read_only(self):
        cost = _pricing.calculate_cost("claude-opus-4.8", 0, 0, cache_read=1_000_000)
        assert cost == pytest.approx(0.50)

    def test_opus_cache_write_5m_only(self):
        cost = _pricing.calculate_cost("claude-opus-4.8", 0, 0, cache_write_5m=1_000_000)
        assert cost == pytest.approx(6.25)

    def test_opus_cache_write_1h_only(self):
        cost = _pricing.calculate_cost("claude-opus-4.8", 0, 0, cache_write_1h=1_000_000)
        assert cost == pytest.approx(10.00)

    def test_opus_combined_cache_buckets(self):
        # 1M read + 2M write_5m + 0.5M write_1h on Opus
        cost = _pricing.calculate_cost(
            "claude-opus-4.8", 0, 0,
            cache_read=1_000_000,
            cache_write_5m=2_000_000,
            cache_write_1h=500_000,
        )
        expected = (1_000_000 * 0.50 + 2_000_000 * 6.25 + 500_000 * 10.00) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_opus_full_example(self):
        # 500k input, 200k output, 100k cache_read, 50k write_5m, 25k write_1h
        cost = _pricing.calculate_cost(
            "claude-opus-4.8",
            inp=500_000,
            outp=200_000,
            cache_read=100_000,
            cache_write_5m=50_000,
            cache_write_1h=25_000,
        )
        expected = (
            500_000 * 5.00
            + 200_000 * 25.00
            + 100_000 * 0.50
            + 50_000 * 6.25
            + 25_000 * 10.00
        ) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_no_cache_args_defaults_to_zero(self):
        cost_with = _pricing.calculate_cost("claude-sonnet-4.6", 1_000_000, 0)
        cost_explicit = _pricing.calculate_cost(
            "claude-sonnet-4.6", 1_000_000, 0, 0, 0, 0
        )
        assert cost_with == pytest.approx(cost_explicit)
        assert cost_with == pytest.approx(3.00)

    def test_baseline_cost_combined(self):
        # Baseline is Opus 4.8: in=$5, out=$25, read=$0.50, write_5m=$6.25, write_1h=$10
        cost = _pricing.baseline_cost(
            inp=1_000_000,
            outp=0,
            cache_read=0,
            cache_write_5m=1_000_000,
            cache_write_1h=0,
        )
        # 1M input=$5 + 1M write_5m=$6.25 = $11.25
        assert cost == pytest.approx(11.25)


# ── transcript fixture builder ────────────────────────────────────────────────

def _ts(offset: float = 0.0) -> str:
    base = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)
    dt = datetime.fromtimestamp(base.timestamp() + offset, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_transcript_dir(tmp_path: Path) -> tuple[Path, str]:
    session_id = str(uuid.uuid4())
    slug = str(tmp_path.resolve()).replace("/", "-")
    proj_dir = tmp_path / ".claude" / "projects" / slug
    proj_dir.mkdir(parents=True)
    return proj_dir, session_id


def _write_jsonl(proj_dir: Path, session_id: str, messages: list[dict]) -> Path:
    path = proj_dir / f"{session_id}.jsonl"
    with path.open("w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return path


def _assistant_entry(
    model: str,
    inp: int,
    outp: int,
    cache_read: int = 0,
    cache_creation_flat: int = 0,
    cache_5m: int = 0,
    cache_1h: int = 0,
    offset: float = 0.0,
) -> dict:
    """Build a synthetic transcript assistant message."""
    usage: dict = {
        "input_tokens": inp,
        "output_tokens": outp,
        "cache_read_input_tokens": cache_read,
    }
    if cache_5m or cache_1h:
        # Structured split
        total_creation = cache_5m + cache_1h
        usage["cache_creation_input_tokens"] = total_creation
        usage["cache_creation"] = {
            "ephemeral_5m_input_tokens": cache_5m,
            "ephemeral_1h_input_tokens": cache_1h,
        }
    elif cache_creation_flat:
        # Flat total only (older transcript format)
        usage["cache_creation_input_tokens"] = cache_creation_flat
    return {
        "type": "assistant",
        "timestamp": _ts(offset),
        "message": {
            "role": "assistant",
            "model": model,
            "usage": usage,
        },
    }


# ── _claude_backend end-to-end tests ─────────────────────────────────────────

class TestClaudeBackendCacheCollection:
    def _run(self, tmp_path, messages, capsys):
        proj_dir, session_id = _make_transcript_dir(tmp_path)
        _write_jsonl(proj_dir, session_id, messages)

        claude_home = tmp_path / ".claude"
        cwd_slug = str(tmp_path.resolve()).replace("/", "-")

        import unittest.mock as mock
        with mock.patch.object(
            _claude_backend, "_resolve_claude_homes", return_value=[claude_home]
        ):
            with mock.patch("pathlib.Path.cwd", return_value=tmp_path):
                rc = _claude_backend.run()

        return rc, capsys.readouterr().out

    def test_5m_1h_split_costs_correctly(self, tmp_path, capsys):
        """Transcript with 5m/1h split prices each bucket at correct rate."""
        # Opus: 1M write_5m @ $6.25 + 1M write_1h @ $10.00 = $16.25
        messages = [
            _assistant_entry(
                "claude-opus-4-8",
                inp=0, outp=0,
                cache_5m=1_000_000,
                cache_1h=1_000_000,
                offset=0.0,
            ),
            _assistant_entry(
                "claude-opus-4-8",
                inp=0, outp=0,
                cache_5m=1_000_000,
                cache_1h=1_000_000,
                offset=1.0,
            ),
        ]
        rc, out = self._run(tmp_path, messages, capsys)
        assert rc == 0
        # 2 messages × (1M write_5m=$6.25 + 1M write_1h=$10) = $32.50
        assert "32.5" in out, f"Expected $32.50 in output, got:\n{out}"

    def test_flat_cache_creation_treated_as_5m(self, tmp_path, capsys):
        """Transcript with only flat cache_creation_input_tokens uses 5m write rate."""
        # Opus: 1M flat creation @ write_5m rate $6.25
        messages = [
            _assistant_entry(
                "claude-opus-4-8",
                inp=0, outp=0,
                cache_creation_flat=1_000_000,
                offset=0.0,
            ),
            _assistant_entry(
                "claude-opus-4-8",
                inp=0, outp=0,
                cache_creation_flat=1_000_000,
                offset=1.0,
            ),
        ]
        rc, out = self._run(tmp_path, messages, capsys)
        assert rc == 0
        # 2 messages × 1M @ $6.25 = $12.50
        assert "12.5" in out, f"Expected $12.50 in output, got:\n{out}"

    def test_no_cache_fields_backward_compat(self, tmp_path, capsys):
        """Old transcripts with no cache fields compute without error."""
        messages = [
            {
                "type": "assistant",
                "timestamp": _ts(0.0),
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
                },
            },
            {
                "type": "assistant",
                "timestamp": _ts(1.0),
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 0, "output_tokens": 1_000_000},
                },
            },
        ]
        rc, out = self._run(tmp_path, messages, capsys)
        assert rc == 0
        # 1M input @ $3 + 1M output @ $15 = $18.00
        assert "18.0" in out, f"Expected $18.00 in output, got:\n{out}"

    def test_cache_read_only_uses_read_rate(self, tmp_path, capsys):
        """cache_read_input_tokens prices at cache_read rate, not write rate."""
        # Opus: 1M cache_read @ $0.50 per message × 2 = $1.00
        messages = [
            _assistant_entry(
                "claude-opus-4-8",
                inp=0, outp=0,
                cache_read=1_000_000,
                offset=0.0,
            ),
            _assistant_entry(
                "claude-opus-4-8",
                inp=0, outp=0,
                cache_read=1_000_000,
                offset=1.0,
            ),
        ]
        rc, out = self._run(tmp_path, messages, capsys)
        assert rc == 0
        # 2M tokens @ $0.50/M = $1.00
        assert "$1.0" in out or "1.0000" in out, f"Expected ~$1.00 in output, got:\n{out}"


class TestWorkedExample:
    """Worked hand-calculation: Opus with N read + M write_5m + K write_1h."""

    def test_opus_hand_calc(self):
        # N=500_000 read, M=800_000 write_5m, K=200_000 write_1h
        # read cost:    500_000 * 0.50 / 1_000_000 = $0.25
        # write_5m:     800_000 * 6.25 / 1_000_000 = $5.00
        # write_1h:     200_000 * 10.00 / 1_000_000 = $2.00
        # total cache: $7.25
        N, M, K = 500_000, 800_000, 200_000
        cost = _pricing.calculate_cost(
            "claude-opus-4.8", 0, 0,
            cache_read=N,
            cache_write_5m=M,
            cache_write_1h=K,
        )
        expected = (N * 0.50 + M * 6.25 + K * 10.00) / 1_000_000
        assert cost == pytest.approx(expected)
        assert cost == pytest.approx(7.25)
