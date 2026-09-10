"""models command — refresh and freeze the model catalog."""

from __future__ import annotations

import fnmatch
import json
import os
import re
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


def _curated(model_id: str, rules: dict, provider: str) -> bool:
    """True iff model_id matches an allow glob and no exclude glob for provider."""
    pf = rules.get("filter", {}).get(provider, {})
    allow = pf.get("allow", [])
    if allow and not any(fnmatch.fnmatch(model_id, pat) for pat in allow):
        return False
    return not _is_excluded(model_id, rules, provider)


def _get_version() -> str:
    from ..config import get_version
    try:
        return get_version()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
_CURATED_PROVIDERS = ("anthropic", "openai")


def _opt_float(value) -> Optional[float]:
    """Coerce *value* to float; None when absent or unparsable (never 0.0)."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opt_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _per_million(price) -> Optional[float]:
    """OpenRouter prices are per-token USD strings; convert to per 1M tokens.

    Rounded to 6 decimals so binary-float noise (0.2 -> 0.19999999999999998)
    never reaches seed.json.
    """
    per_token = _opt_float(price)
    return None if per_token is None else round(per_token * 1_000_000, 6)


def _created_at(created) -> Optional[str]:
    ts = _opt_int(created)
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def _enrichment(m: dict) -> dict:
    """Capability/price/recency fields carried on every seed entry.

    A missing benchmark stays null — a real 0.0 score exists upstream and
    collapsing missing into 0.0 would corrupt the ranking.
    """
    bench = (m.get("benchmarks") or {}).get("artificial_analysis") or {}
    pricing = m.get("pricing") or {}
    return {
        "coding_index": _opt_float(bench.get("coding_index")),
        "intelligence_index": _opt_float(bench.get("intelligence_index")),
        "price_in": _per_million(pricing.get("prompt")),
        "price_out": _per_million(pricing.get("completion")),
        "context_length": _opt_int(m.get("context_length")),
        "created_at": _created_at(m.get("created")),
    }


def _rank(entries: list[dict]) -> list[dict]:
    """Sort frontier→lowest by coding_index (nulls last, id order) and rank."""
    ordered = sorted(
        entries,
        key=lambda e: (
            e.get("coding_index") is None,
            -(e.get("coding_index") or 0.0),
            e["id"],
        ),
    )
    for i, entry in enumerate(ordered, start=1):
        entry["rank"] = i
    return ordered


def _fetch_openrouter(rules: dict, *, url: str = _OPENROUTER_URL) -> dict[str, list[dict]]:
    """Fetch the public OpenRouter model list (no auth) and return curated,
    provider-native seed entries keyed by provider.

    Anthropic ids: strip 'anthropic/', convert dots->dashes. OpenAI ids: strip
    'openai/', keep dots. Every entry carries a cleaned display_name (when the
    source provides one) plus coding_index, intelligence_index, price_in, price_out,
    context_length, created_at and a 1-based rank. Non-curated prefixes are
    ignored.
    """
    import urllib.request

    version = _get_version()
    req = urllib.request.Request(url, headers={"User-Agent": f"agent-notes/{version}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read(16 * 1024 * 1024))

    out: dict[str, list[dict]] = {p: [] for p in _CURATED_PROVIDERS}
    for m in data.get("data", []):
        mid = m.get("id", "")
        prov, _, rest = mid.partition("/")
        if prov not in _CURATED_PROVIDERS or not rest:
            continue
        native = rest.replace(".", "-") if prov == "anthropic" else rest
        if not re.fullmatch(r"[A-Za-z0-9.\-]+", native):
            continue  # untrusted OpenRouter input: drop ids with newlines/slashes/control chars
        if not _curated(native, rules, prov):
            continue
        entry = {"id": native}
        raw_name = m.get("name")
        if prov == "anthropic":
            name = raw_name or native
            if name.startswith("Anthropic:"):
                name = name[len("Anthropic:"):].strip()
            entry["display_name"] = "".join(ch for ch in name if ch.isprintable())
        elif raw_name:
            name = raw_name
            if name.startswith("OpenAI:"):
                name = name[len("OpenAI:"):].strip()
            entry["display_name"] = "".join(ch for ch in name if ch.isprintable())
        entry.update(_enrichment(m))
        out[prov].append(entry)
    return {prov: _rank(entries) for prov, entries in out.items()}


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
    """Fetch the model catalog from OpenRouter (keyless), show the diff, write cache.

    - ``--provider anthropic|openai``  limit output to one provider
    - ``--dry-run``                    print diff but write nothing
    No credentials are used; OpenRouter's model list is public.
    """
    rules = _load_rules()
    old_catalog = _load_current_catalog()

    print("Fetching from OpenRouter...")
    try:
        fetched = _fetch_openrouter(rules)
    except Exception as exc:  # network/parse failure -> loud, non-zero (CI guard)
        print(f"  fetch failed — {type(exc).__name__}: {exc}")
        sys.exit(1)

    if provider is not None:
        fetched = {provider: fetched.get(provider, [])}

    new_providers = {p: e for p, e in fetched.items() if e}
    for p in fetched:
        print(f"  {p}: {len(fetched[p])} models")
    if not new_providers:
        print("Nothing fetched.")
        sys.exit(1)

    new_catalog = {
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
