"""Tests for agent-notes models refresh / freeze command."""

from __future__ import annotations

import json
import sys
import warnings
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal urllib HTTP response double."""

    def __init__(self, payload: dict | list):
        self._body = json.dumps(payload).encode()

    def read(self, size: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# _fetch_openrouter
# ---------------------------------------------------------------------------

_OR_PAYLOAD = {"data": [
    {"id": "anthropic/claude-opus-4.8", "name": "Anthropic: Claude Opus 4.8"},
    {"id": "anthropic/claude-opus-5",   "name": "Claude Opus 5"},
    {"id": "anthropic/claude-opus-5-fast", "name": "Claude Opus 5 (Fast)"},
    {"id": "anthropic/claude-3-haiku",  "name": "Anthropic: Claude 3 Haiku"},
    {"id": "openai/gpt-5.5",            "name": "OpenAI: GPT-5.5"},
    {"id": "openai/gpt-5.4-mini",       "name": "OpenAI: GPT-5.4 Mini"},
    {"id": "openai/gpt-5.6-luna",       "name": "OpenAI: GPT-5.6 Luna"},
    {"id": "openai/gpt-5-nano",         "name": "OpenAI: GPT-5 Nano"},
    {"id": "google/gemini-3-pro",       "name": "Google: Gemini 3 Pro"},
]}

_RULES = {"filter": {
    "anthropic": {"allow": ["claude-opus-*", "claude-sonnet-*", "claude-haiku-*", "claude-fable-*"],
                  "exclude": ["*-fast", "claude-3-*", "claude-opus-4"]},
    "openai":    {"allow": ["gpt-5*"], "exclude": ["*-luna*", "*-nano", "gpt-5-mini", "gpt-5"]},
}}


class TestFetchOpenRouter:
    def test_fetch_openrouter_maps_and_curates(self):
        from agent_notes.commands.models import _fetch_openrouter
        with patch("urllib.request.urlopen", side_effect=lambda *a, **k: _FakeResponse(_OR_PAYLOAD)):
            got = _fetch_openrouter(_RULES)
        anth_ids = {e["id"] for e in got["anthropic"]}
        oai_ids  = {e["id"] for e in got["openai"]}
        assert anth_ids == {"claude-opus-4-8", "claude-opus-5"}      # dots->dashes; -fast & claude-3 dropped
        assert oai_ids  == {"gpt-5.5", "gpt-5.4-mini"}               # keep dots; -luna & -nano dropped
        assert "google" not in got                                   # non-curated provider ignored
        opus48 = next(e for e in got["anthropic"] if e["id"] == "claude-opus-4-8")
        assert opus48["display_name"] == "Claude Opus 4.8"           # "Anthropic: " prefix stripped
        assert opus48["created_at"] is None
        assert all(set(e.keys()) == {"id"} for e in got["openai"])   # openai entries are id-only

    def test_refresh_fails_loud_on_empty(self, monkeypatch, tmp_path):
        # OpenRouter returns nothing curated -> refresh must sys.exit(1) (CI guard)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        from agent_notes.commands import models
        monkeypatch.setattr(models, "_fetch_openrouter", lambda rules: {"anthropic": [], "openai": []})
        with pytest.raises(SystemExit) as ei:
            models.refresh()
        assert ei.value.code == 1

    def test_fetch_openrouter_rejects_malicious_ids(self):
        payload = {"data": [
            {"id": "anthropic/claude-sonnet-4\nmodel: evil", "name": "Anthropic: Evil"},
            {"id": "anthropic/claude-sonnet-5", "name": "Anthropic: Claude Sonnet 5"},
        ]}
        from agent_notes.commands.models import _fetch_openrouter
        with patch("urllib.request.urlopen", side_effect=lambda *a, **k: _FakeResponse(payload)):
            got = _fetch_openrouter(_RULES)
        anth_ids = {e["id"] for e in got["anthropic"]}
        assert "claude-sonnet-4\nmodel: evil" not in anth_ids
        assert "claude-sonnet-5" in anth_ids


# ---------------------------------------------------------------------------
# refresh — dry-run writes nothing
# ---------------------------------------------------------------------------

class TestRefreshDryRun:
    def test_dry_run_writes_no_files(self, tmp_path, monkeypatch):
        """--dry-run must not create any files under XDG_CACHE_HOME."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        fake_fetched = {
            "anthropic": [{"id": "claude-opus-4-8", "display_name": "Claude Opus 4.8", "created_at": None}],
            "openai": [{"id": "gpt-5.5"}],
        }

        with patch("agent_notes.commands.models._load_rules", return_value={}), \
             patch("agent_notes.commands.models._load_current_catalog", return_value={"providers": {}}), \
             patch("agent_notes.commands.models._fetch_openrouter", return_value=fake_fetched):
            from agent_notes.commands.models import refresh
            refresh(dry_run=True)

        cache = tmp_path / "agent-notes" / "catalog.json"
        assert not cache.exists(), "dry-run must write nothing"


# ---------------------------------------------------------------------------
# catalog_loader — corrupt cache falls back to seed
# ---------------------------------------------------------------------------

class TestCatalogLoaderCorruptCache:
    def test_corrupt_cache_falls_back_to_seed(self, tmp_path, monkeypatch):
        """A corrupt cache emits a warning and loads from the bundled seed.json."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        cache_dir = tmp_path / "agent-notes"
        cache_dir.mkdir()
        (cache_dir / "catalog.json").write_text("{ this is not valid json !!! }")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            from agent_notes.registries.catalog_loader import load_catalog
            models = load_catalog()

        assert len(models) > 0, "Should load from seed.json after corrupt cache"
        messages = [str(w.message) for w in caught]
        assert any("corrupt" in m.lower() or "invalid" in m.lower() for m in messages), (
            f"Expected a warning about corrupt cache. Got: {messages}"
        )

    def test_valid_cache_is_preferred_over_seed(self, tmp_path, monkeypatch):
        """A valid cache is loaded instead of seed.json."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        cache_dir = tmp_path / "agent-notes"
        cache_dir.mkdir()

        # Use an id that matches existing class/family rules (claude-* → claude family,
        # *sonnet* → sonnet class) so catalog_loader can build a Model from it.
        fake_catalog = {
            "fetched_at": "2099-01-01T00:00:00Z",
            "providers": {
                "anthropic": [
                    {
                        "id": "claude-sonnet-99",
                        "display_name": "Claude Sonnet 99 (cache test)",
                        "created_at": "2099-01-01T00:00:00Z",
                    }
                ]
            }
        }
        (cache_dir / "catalog.json").write_text(json.dumps(fake_catalog))

        from agent_notes.registries.catalog_loader import load_catalog
        models = load_catalog()

        ids = [m.id for m in models]
        assert "claude-sonnet-99" in ids

    def test_explicit_catalog_dir_bypasses_cache(self, tmp_path, monkeypatch):
        """When catalog_dir is explicit, cache is not consulted."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        # Poison the cache with a different model
        cache_dir = tmp_path / "agent-notes"
        cache_dir.mkdir()
        poison = {
            "fetched_at": "2099-01-01T00:00:00Z",
            "providers": {"anthropic": [
                {"id": "poison-model", "display_name": "Poison", "created_at": None}
            ]}
        }
        (cache_dir / "catalog.json").write_text(json.dumps(poison))

        from agent_notes.config import DATA_DIR
        from agent_notes.registries.catalog_loader import load_catalog

        # Passing an explicit catalog_dir should use its seed.json, not the cache
        models = load_catalog(catalog_dir=DATA_DIR / "catalog")
        ids = [m.id for m in models]
        assert "poison-model" not in ids


# ---------------------------------------------------------------------------
# build makes no network call
# ---------------------------------------------------------------------------

class TestBuildNoNetworkCall:
    def test_build_never_calls_urlopen(self, tmp_path, monkeypatch):
        """agent-notes build must not invoke urllib.request.urlopen at all."""
        # Ensure no live cache (so catalog_loader uses seed.json)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        def _forbidden(*args, **kwargs):
            raise AssertionError(
                "build() made a network call via urllib.request.urlopen — "
                "only `models refresh` may touch the network"
            )

        with patch("urllib.request.urlopen", side_effect=_forbidden):
            from agent_notes.commands.build import build
            build()  # must not raise


# ---------------------------------------------------------------------------
# freeze
# ---------------------------------------------------------------------------

class TestFreeze:
    def test_freeze_copies_cache_to_seed(self, tmp_path, monkeypatch):
        """freeze() writes the cache content to seed.json."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        cache_dir = tmp_path / "agent-notes"
        cache_dir.mkdir()
        fake = {"fetched_at": "2099-01-01T00:00:00Z", "providers": {"anthropic": []}}
        (cache_dir / "catalog.json").write_text(json.dumps(fake))

        fake_seed = tmp_path / "seed.json"

        with patch("agent_notes.commands.models._get_seed_path", return_value=fake_seed):
            from agent_notes.commands.models import freeze
            freeze()

        written = json.loads(fake_seed.read_text())
        assert written["fetched_at"] == "2099-01-01T00:00:00Z"

    def test_freeze_exits_when_no_cache(self, tmp_path, monkeypatch):
        """freeze() exits with code 1 when no cache exists."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        # No cache file created

        with pytest.raises(SystemExit) as exc_info:
            from agent_notes.commands.models import freeze
            freeze()

        assert exc_info.value.code == 1
