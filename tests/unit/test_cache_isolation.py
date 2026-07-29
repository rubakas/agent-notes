"""Cache isolation tests.

These tests verify that the session-level XDG_CACHE_HOME isolation wired in
conftest.py prevents a developer's personal ~/.cache/agent-notes/catalog.json
from contaminating the test suite.

Fail-first contract:
    Without the conftest.py fix (pytest_configure setting XDG_CACHE_HOME before
    pytest_sessionstart), load_catalog() resolves to ~/.cache/agent-notes/ and
    any test that calls it would read machine-local state.  The test below
    demonstrates this concretely by planting a bogus catalog at the real home
    cache and asserting it does *not* appear in the registry.  On unfixed code
    the bogus model *is* returned and the assertion fails.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_notes.registries.catalog_loader import load_catalog


class TestHomeCacheIsolation:
    """Session XDG_CACHE_HOME isolation guards against real developer caches."""

    def test_real_home_cache_is_not_read(self):
        """A catalog planted at ~/.cache/agent-notes/catalog.json must not
        influence the registry when session-level cache isolation is active.

        Without isolation (XDG_CACHE_HOME unset), load_catalog() resolves to
        Path.home() / '.cache' and the planted bogus model shows up in the
        result — making this assertion fail.  With isolation in conftest.py,
        XDG_CACHE_HOME points to the session temp dir (which has no cache),
        so load_catalog() falls back to the packaged seed.json and the bogus
        model is absent.
        """
        real_cache_dir = Path.home() / ".cache" / "agent-notes"
        real_cache_path = real_cache_dir / "catalog.json"

        # Snapshot any pre-existing cache so we can restore it afterwards.
        existing: bytes | None = (
            real_cache_path.read_bytes() if real_cache_path.exists() else None
        )

        # "claude-sonnet-fake-9" satisfies the catalog rules:
        #   claude-*    → family: claude
        #   *sonnet*    → class: sonnet
        # Any id that does NOT match a family or class rule would raise
        # ValueError inside load_catalog(), which is a different failure mode
        # from what we're testing here.
        bogus_id = "claude-sonnet-fake-9"
        bogus_catalog = {
            "fetched_at": "2020-01-01T00:00:00Z",
            "providers": {
                "anthropic": [
                    {
                        "id": bogus_id,
                        "display_name": "Claude Sonnet Fake 9 (isolation probe)",
                        "created_at": "2020-01-01T00:00:00Z",
                    }
                ]
            },
        }

        try:
            real_cache_dir.mkdir(parents=True, exist_ok=True)
            real_cache_path.write_text(json.dumps(bogus_catalog))

            models = load_catalog()
            ids = [m.id for m in models]

            assert bogus_id not in ids, (
                f"Model '{bogus_id}' from ~/.cache/agent-notes/catalog.json leaked "
                "into the registry.  Session-level XDG_CACHE_HOME isolation in "
                "conftest.py is missing or not applied early enough to cover the "
                "pytest_sessionstart build subprocess."
            )
        finally:
            if existing is None:
                real_cache_path.unlink(missing_ok=True)
            else:
                real_cache_path.write_bytes(existing)

    def test_xdg_cache_home_is_not_real_home_cache(self):
        """XDG_CACHE_HOME must be set and must not resolve to ~/.cache.

        This is a quick sanity-check that the conftest.py isolation is in place.
        It doesn't exercise load_catalog() but makes the misconfiguration visible
        immediately with a clear error message.
        """
        xdg = os.environ.get("XDG_CACHE_HOME", "")
        real_home_cache = Path.home() / ".cache"

        assert xdg, (
            "XDG_CACHE_HOME is not set.  conftest.py must set it (via "
            "pytest_configure) before pytest_sessionstart so the build "
            "subprocess also inherits the isolation."
        )

        assert Path(xdg).resolve() != real_home_cache.resolve(), (
            f"XDG_CACHE_HOME is set to the real home cache ({xdg!r}).  "
            "It must point to a session-scoped temp directory instead."
        )
