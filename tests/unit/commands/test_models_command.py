"""Tests for agent-notes models refresh / freeze command."""

from __future__ import annotations

import json
import sys
import warnings
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal urllib HTTP response double."""

    def __init__(self, payload: dict | list):
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _make_credentials(configured: dict[str, str | None]):
    """Return (is_configured, get) mocks driven by *configured* dict.

    Keys are provider names; values are API keys (None = not configured).
    """
    def _is_configured(provider: str) -> bool:
        return provider in configured and configured[provider] is not None

    def _get(provider: str):
        return configured.get(provider)

    return _is_configured, _get


# ---------------------------------------------------------------------------
# _fetch_anthropic
# ---------------------------------------------------------------------------

ANTHROPIC_PAGE_1 = {
    "data": [
        {
            "id": "claude-sonnet-5",
            "display_name": "Claude Sonnet 5",
            "created_at": "2026-01-01T00:00:00Z",
            "max_input_tokens": 200000,
            "max_tokens": 8192,
            "type": "model",
        },
        {
            "id": "claude-opus-4-8",
            "display_name": "Claude Opus 4.8",
            "created_at": "2025-12-01T00:00:00Z",
            "max_input_tokens": 0,   # unknown — must not be stored
            "max_tokens": 4096,
            "type": "model",
        },
    ],
    "has_more": True,
    "first_id": "claude-sonnet-5",
    "last_id": "claude-opus-4-8",
}

ANTHROPIC_PAGE_2 = {
    "data": [
        {
            "id": "claude-haiku-4-5",
            "display_name": "Claude Haiku 4.5",
            "created_at": "2025-06-01T00:00:00Z",
            "max_input_tokens": 100000,
            "max_tokens": 4096,
            "type": "model",
        },
    ],
    "has_more": False,
    "first_id": "claude-haiku-4-5",
    "last_id": "claude-haiku-4-5",
}


class TestFetchAnthropic:
    def test_pagination_assembles_full_list(self):
        """Two pages of results are concatenated into a single list."""
        responses = [_FakeResponse(ANTHROPIC_PAGE_1), _FakeResponse(ANTHROPIC_PAGE_2)]
        call_count = [0]

        def fake_urlopen(req, timeout=None):
            resp = responses[call_count[0]]
            call_count[0] += 1
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            from agent_notes.commands.models import _fetch_anthropic
            entries = _fetch_anthropic("sk-fake-key")

        assert len(entries) == 3
        ids = [e["id"] for e in entries]
        assert "claude-sonnet-5" in ids
        assert "claude-opus-4-8" in ids
        assert "claude-haiku-4-5" in ids

    def test_pagination_uses_after_id_on_second_request(self):
        """Second request URL contains after_id=<last_id from page 1>."""
        responses = [_FakeResponse(ANTHROPIC_PAGE_1), _FakeResponse(ANTHROPIC_PAGE_2)]
        call_count = [0]
        urls_seen: list[str] = []

        def fake_urlopen(req, timeout=None):
            urls_seen.append(req.full_url)
            resp = responses[call_count[0]]
            call_count[0] += 1
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            from agent_notes.commands.models import _fetch_anthropic
            _fetch_anthropic("sk-fake-key")

        assert len(urls_seen) == 2
        assert "after_id=claude-opus-4-8" in urls_seen[1]

    def test_max_input_tokens_zero_not_stored(self):
        """max_input_tokens: 0 from the API is treated as unknown and omitted."""
        responses = [_FakeResponse(ANTHROPIC_PAGE_1), _FakeResponse(ANTHROPIC_PAGE_2)]
        call_count = [0]

        def fake_urlopen(req, timeout=None):
            resp = responses[call_count[0]]
            call_count[0] += 1
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            from agent_notes.commands.models import _fetch_anthropic
            entries = _fetch_anthropic("sk-fake-key")

        opus = next(e for e in entries if e["id"] == "claude-opus-4-8")
        assert "max_input_tokens" not in opus

    def test_max_input_tokens_nonzero_is_stored(self):
        """max_input_tokens with a real value is preserved."""
        responses = [_FakeResponse(ANTHROPIC_PAGE_1), _FakeResponse(ANTHROPIC_PAGE_2)]
        call_count = [0]

        def fake_urlopen(req, timeout=None):
            resp = responses[call_count[0]]
            call_count[0] += 1
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            from agent_notes.commands.models import _fetch_anthropic
            entries = _fetch_anthropic("sk-fake-key")

        sonnet = next(e for e in entries if e["id"] == "claude-sonnet-5")
        assert sonnet["max_input_tokens"] == 200000

    def test_single_page_no_has_more(self):
        """A single-page response (has_more=False) makes exactly one request."""
        single_page = dict(ANTHROPIC_PAGE_2, has_more=False)
        call_count = [0]

        def fake_urlopen(req, timeout=None):
            call_count[0] += 1
            return _FakeResponse(single_page)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            from agent_notes.commands.models import _fetch_anthropic
            entries = _fetch_anthropic("sk-fake-key")

        assert call_count[0] == 1
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# _fetch_openai
# ---------------------------------------------------------------------------

OPENAI_RESPONSE = {
    "object": "list",
    "data": [
        {"id": "gpt-5.5",           "object": "model", "created": 1700000001, "owned_by": "openai"},
        {"id": "gpt-5.4",           "object": "model", "created": 1700000000, "owned_by": "openai"},
        {"id": "gpt-5.4-mini",      "object": "model", "created": 1699999999, "owned_by": "openai"},
        # noise — must be filtered out
        {"id": "text-embedding-ada-002", "object": "model", "created": 1698000000, "owned_by": "openai"},
        {"id": "tts-1",                  "object": "model", "created": 1698000001, "owned_by": "openai"},
        {"id": "whisper-1",              "object": "model", "created": 1698000002, "owned_by": "openai"},
        {"id": "dall-e-3",               "object": "model", "created": 1698000003, "owned_by": "openai"},
        {"id": "gpt-4-instruct",         "object": "model", "created": 1698000004, "owned_by": "openai"},
    ],
}

_RULES_WITH_OPENAI_FILTER = {
    "filter": {
        "openai": {
            "exclude": [
                "text-embedding-*",
                "tts-*",
                "whisper-*",
                "dall-e-*",
                "*-instruct",
                "*search*",
                "*realtime*",
            ]
        }
    }
}


class TestFetchOpenAI:
    def _do_fetch(self):
        from agent_notes.commands.models import _fetch_openai

        def fake_urlopen(req, timeout=None):
            return _FakeResponse(OPENAI_RESPONSE)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            return _fetch_openai("sk-fake-key", _RULES_WITH_OPENAI_FILTER)

    def test_chat_models_included(self):
        entries = self._do_fetch()
        ids = [e["id"] for e in entries]
        assert "gpt-5.5" in ids
        assert "gpt-5.4" in ids
        assert "gpt-5.4-mini" in ids

    def test_noise_models_excluded(self):
        entries = self._do_fetch()
        ids = [e["id"] for e in entries]
        assert "text-embedding-ada-002" not in ids
        assert "tts-1" not in ids
        assert "whisper-1" not in ids
        assert "dall-e-3" not in ids
        assert "gpt-4-instruct" not in ids

    def test_total_count_matches_chat_models_only(self):
        entries = self._do_fetch()
        assert len(entries) == 3

    def test_created_timestamp_preserved(self):
        entries = self._do_fetch()
        gpt55 = next(e for e in entries if e["id"] == "gpt-5.5")
        assert gpt55["created"] == 1700000001


# ---------------------------------------------------------------------------
# refresh — unconfigured provider is skipped gracefully
# ---------------------------------------------------------------------------

class TestRefreshUnconfiguredProvider:
    def test_skips_unconfigured_with_named_message(self, capsys, tmp_path, monkeypatch):
        """Both providers unconfigured: prints name-only skip message, fetches nothing."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        is_configured, get_key = _make_credentials({})  # nothing configured

        with patch("agent_notes.commands.models._load_rules", return_value=_RULES_WITH_OPENAI_FILTER), \
             patch("agent_notes.commands.models._load_current_catalog", return_value={"providers": {}}), \
             patch("agent_notes.services.credentials.is_configured", side_effect=is_configured), \
             patch("agent_notes.services.credentials.get", side_effect=get_key), \
             patch("urllib.request.urlopen") as mock_urlopen:
            from agent_notes.commands.models import refresh
            refresh(dry_run=True)
            mock_urlopen.assert_not_called()

        out = capsys.readouterr().out
        assert "anthropic" in out
        assert "not configured" in out
        assert "openai" in out

    def test_api_key_never_in_output(self, capsys, tmp_path, monkeypatch):
        """Even when an API key exists, it must not appear in printed output."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        secret = "SECRET-API-KEY-12345"

        is_configured, get_key = _make_credentials({"anthropic": secret})

        page = {"data": [], "has_more": False}

        with patch("agent_notes.commands.models._load_rules", return_value=_RULES_WITH_OPENAI_FILTER), \
             patch("agent_notes.commands.models._load_current_catalog", return_value={"providers": {}}), \
             patch("agent_notes.services.credentials.is_configured", side_effect=is_configured), \
             patch("agent_notes.services.credentials.get", side_effect=get_key), \
             patch("urllib.request.urlopen", return_value=_FakeResponse(page)):
            from agent_notes.commands.models import refresh
            refresh(provider="anthropic", dry_run=True)

        out, err = capsys.readouterr()
        assert secret not in out
        assert secret not in err


# ---------------------------------------------------------------------------
# refresh — dry-run writes nothing
# ---------------------------------------------------------------------------

class TestRefreshDryRun:
    def test_dry_run_writes_no_files(self, tmp_path, monkeypatch):
        """--dry-run must not create any files under XDG_CACHE_HOME."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        secret = "sk-dry-run-test"
        is_configured, get_key = _make_credentials(
            {"anthropic": secret, "openai": secret}
        )

        responses = [
            _FakeResponse({"data": [], "has_more": False}),
            _FakeResponse({"object": "list", "data": []}),
        ]
        call_count = [0]

        def fake_urlopen(req, timeout=None):
            r = responses[call_count[0] % len(responses)]
            call_count[0] += 1
            return r

        with patch("agent_notes.commands.models._load_rules", return_value=_RULES_WITH_OPENAI_FILTER), \
             patch("agent_notes.commands.models._load_current_catalog", return_value={"providers": {}}), \
             patch("agent_notes.services.credentials.is_configured", side_effect=is_configured), \
             patch("agent_notes.services.credentials.get", side_effect=get_key), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
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
