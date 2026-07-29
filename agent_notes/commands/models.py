"""models command — refresh and freeze the model catalog."""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _get_cache_path() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "agent-notes" / "catalog.json"


def _get_seed_path() -> Path:
    from ..config import DATA_DIR
    return DATA_DIR / "catalog" / "seed.json"


def _load_rules() -> dict:
    from ..config import DATA_DIR
    import yaml
    rules_path = DATA_DIR / "catalog" / "rules.yaml"
    return yaml.safe_load(rules_path.read_text()) or {}


def _is_excluded(model_id: str, rules: dict, provider: str) -> bool:
    """Return True if *model_id* matches any exclude pattern for *provider*."""
    exclude_patterns = rules.get("filter", {}).get(provider, {}).get("exclude", [])
    return any(fnmatch.fnmatch(model_id, pat) for pat in exclude_patterns)


def _get_version() -> str:
    from ..config import get_version
    try:
        return get_version()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_anthropic(api_key: str) -> list[dict]:
    """Fetch all models from Anthropic API with cursor pagination.

    Returns a list of seed-format entries:
    ``{"id": ..., "display_name": ..., "created_at": ...}``

    ``max_input_tokens: 0`` from the API means unknown; it is not stored.
    """
    import urllib.request

    version = _get_version()
    base_url = "https://api.anthropic.com/v1/models"
    entries: list[dict] = []
    after_id: Optional[str] = None

    while True:
        url = f"{base_url}?limit=1000"
        if after_id:
            url += f"&after_id={after_id}"

        req = urllib.request.Request(
            url,
            headers={
                "anthropic-version": "2023-06-01",
                "x-api-key": api_key,
                "User-Agent": f"agent-notes/{version}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        for m in data.get("data", []):
            entry: dict = {
                "id": m["id"],
                "display_name": m.get("display_name") or m["id"],
                "created_at": m.get("created_at"),
            }
            max_input = m.get("max_input_tokens")
            if max_input and max_input != 0:
                entry["max_input_tokens"] = max_input
            entries.append(entry)

        if not data.get("has_more"):
            break
        after_id = data.get("last_id")
        if not after_id:
            break

    return entries


def _fetch_openai(api_key: str, rules: dict) -> list[dict]:
    """Fetch chat models from OpenAI API (unpaginated).

    Non-chat models (embeddings, TTS, Whisper, DALL·E, etc.) are filtered
    using the ``filter.openai.exclude`` patterns in ``rules.yaml``.

    Returns a list of seed-format entries: ``{"id": ..., "created": ...}``
    """
    import urllib.request

    version = _get_version()
    req = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"agent-notes/{version}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    entries: list[dict] = []
    for m in data.get("data", []):
        model_id = m["id"]
        if _is_excluded(model_id, rules, "openai"):
            continue
        entry: dict = {"id": model_id}
        created = m.get("created")
        if created is not None:
            entry["created"] = created
        entries.append(entry)

    return entries


def _load_current_catalog() -> dict:
    """Load current catalog: cache if present and valid, else seed.json."""
    from ..config import DATA_DIR
    import warnings

    cache_path = _get_cache_path()
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            warnings.warn(f"Cache at {cache_path} is corrupt ({e}); using seed.json")

    seed_path = DATA_DIR / "catalog" / "seed.json"
    with open(seed_path) as f:
        return json.load(f)


def _print_diff(old: dict, new_catalog: dict, providers: list[str]) -> None:
    """Print a human-readable diff of model changes per provider."""
    any_change = False
    for provider in providers:
        old_entries = {e["id"]: e for e in old.get("providers", {}).get(provider, [])}
        new_entries = {e["id"]: e for e in new_catalog.get("providers", {}).get(provider, [])}

        added = sorted(eid for eid in new_entries if eid not in old_entries)
        removed = sorted(eid for eid in old_entries if eid not in new_entries)
        changed = sorted(
            eid for eid in new_entries
            if eid in old_entries and new_entries[eid] != old_entries[eid]
        )

        if not (added or removed or changed):
            print(f"  {provider}: no changes")
            continue

        any_change = True
        for eid in added:
            label = new_entries[eid].get("display_name") or eid
            print(f"  + {provider}/{eid}  ({label})")
        for eid in removed:
            label = old_entries[eid].get("display_name") or eid
            print(f"  - {provider}/{eid}  ({label})")
        for eid in changed:
            print(f"  ~ {provider}/{eid}  (updated)")


def refresh(provider: Optional[str] = None, dry_run: bool = False) -> None:
    """Fetch model catalog from provider APIs, show diff, and write cache.

    - ``--provider anthropic|openai``  limit to one provider
    - ``--dry-run``                    print diff but write nothing

    Auth is read from the credentials store via ``is_configured`` / ``get``.
    Unconfigured providers are skipped by name; the key value is never printed.
    """
    from ..services import credentials

    providers = ["anthropic", "openai"] if provider is None else [provider]
    rules = _load_rules()
    old_catalog = _load_current_catalog()

    new_providers: dict = {}
    for p in providers:
        if not credentials.is_configured(p):
            print(f"  {p}: not configured — skipping")
            continue
        api_key = credentials.get(p)
        if not api_key:
            print(f"  {p}: key is empty — skipping")
            continue
        print(f"Fetching {p}...")
        try:
            if p == "anthropic":
                entries = _fetch_anthropic(api_key)
            else:
                entries = _fetch_openai(api_key, rules)
        except Exception as exc:
            print(f"  {p}: fetch failed — {type(exc).__name__}: {exc}")
            continue
        new_providers[p] = entries
        print(f"  {p}: fetched {len(entries)} models")

    if not new_providers:
        print("Nothing fetched.")
        return

    # Merge: carry over providers we didn't refresh
    new_catalog: dict = {
        "fetched_at": _now_iso(),
        "providers": {**old_catalog.get("providers", {}), **new_providers},
    }

    print("\nDiff:")
    _print_diff(old_catalog, new_catalog, list(new_providers.keys()))

    if dry_run:
        print("\n(dry-run: nothing written)")
        return

    cache_path = _get_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(new_catalog, indent=2))
    print(f"\nWrote {cache_path}")


def freeze() -> None:
    """Promote the live cache to the bundled seed.json.

    Workflow: ``models refresh`` → review diff → ``models freeze`` → commit.
    """
    cache_path = _get_cache_path()
    if not cache_path.exists():
        print("No cache found. Run `agent-notes models refresh` first.")
        sys.exit(1)

    try:
        data = json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Cache is invalid: {exc}")
        sys.exit(1)

    seed_path = _get_seed_path()
    seed_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Froze cache to {seed_path}")
