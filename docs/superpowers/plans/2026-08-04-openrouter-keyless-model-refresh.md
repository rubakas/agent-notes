# Keyless OpenRouter Model-Catalog Refresh + Scheduled Auto-PR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two credentialed direct-provider fetchers in `agent-notes models refresh` with a single **keyless** OpenRouter source (`https://openrouter.ai/api/v1/models`), curated by allowlist+exclude globs, and add a dev script + a scheduled CI workflow that opens a PR when the model list actually changes — all with **zero credentials**.

**Architecture:** `refresh` fetches once from OpenRouter (no auth), partitions models by `anthropic/` and `openai/` id-prefix, maps each slug to the provider-native id (Anthropic: dots→dashes; OpenAI: keep dots), and keeps a model only if it matches a provider `allow` glob and no `exclude` glob in `rules.yaml`. The `filter` block is **refresh-only** (build reads pre-filtered `seed.json`), so this change is **byte-identical for build output**. A `scripts/dev/update-models` wrapper runs refresh→freeze from source; `.github/workflows/update-models.yml` runs it on a weekly cron and opens/updates one PR against `develop`, gated on a real model-list change (ignoring the `fetched_at` timestamp).

**Tech Stack:** Python 3.11+ (stdlib `urllib`), pytest, GitHub Actions (`astral-sh/setup-uv`, `peter-evans/create-pull-request`), bash.

## Global Constraints

- **No credentials anywhere.** The OpenRouter endpoint returns HTTP 200 unauthenticated. `refresh` must NOT import or call `agent_notes.services.credentials`. The CI workflow must NOT reference any secret.
- **Build stays byte-identical.** Do NOT modify `agent_notes/data/catalog/seed.json` in this work. `rules.yaml` changes are confined to the `filter:` block, which only affects `refresh` (per the file's own comment: "Build reads seed.json (pre-filtered) and is never affected"). Verify with `scripts/dev/verify_dist_equiv.sh <baseline>` → BYTE-IDENTICAL.
- **Full suite green.** `uv run pytest tests/` passes. Tests for the removed fetchers are replaced, not merely deleted-with-coverage-loss.
- **Curation policy (locked):**
  - Anthropic — allow `claude-opus-*`, `claude-sonnet-*`, `claude-haiku-*`, `claude-fable-*`; exclude `*-fast`, `claude-3-*`, `claude-opus-4`. → your 11 + `claude-opus-5`.
  - OpenAI — allow `gpt-5*`; exclude `*-image*`, `*-audio*`, `*-codex*`, `*-pro`, `*-nano`, `*-luna*`, `*-terra*`, `*-sol*`, `*-chat*`, `*:free`, `*oss*`, `*-instruct`, `gpt-5-mini`, `gpt-5`. → `gpt-5.1`, `gpt-5.2`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5`.
- **No AI attribution** in commits, PR titles, or PR bodies (no `Co-Authored-By`, no "Generated with", no 🤖).
- **Entry schema (list-only, match current seed shape):** Anthropic `{"id", "display_name", "created_at": null}`; OpenAI `{"id"}`. No recency/pricing enrichment in this phase.

---

### Task A: Keyless OpenRouter source for `models refresh`

**Files:**
- Modify: `agent_notes/data/catalog/rules.yaml` (expand the `filter:` block)
- Modify: `agent_notes/commands/models.py` (add `_fetch_openrouter` + curation helper; rewrite `refresh`; delete `_fetch_anthropic`, `_fetch_openai`, and the `credentials` import)
- Modify: `agent_notes/cli.py` (only if the `refresh` signature/args change — keep `--provider {anthropic,openai}` and `--dry-run`)
- Test: `tests/unit/commands/test_models_command.py` (replace fetch/credentials tests)

**Interfaces:**
- Produces: `_fetch_openrouter(rules: dict, *, url: str = "https://openrouter.ai/api/v1/models") -> dict[str, list[dict]]` returning `{"anthropic": [...], "openai": [...]}` (only curated providers, only kept models).
- Produces: `_curated(model_id: str, rules: dict, provider: str) -> bool` (True iff matches an `allow` glob and no `exclude` glob).
- `refresh(provider: Optional[str] = None, dry_run: bool = False) -> None` — unchanged signature; now keyless and fails loud (`sys.exit(1)`) on fetch error or empty result.
- Consumes: existing `_load_rules`, `_load_current_catalog`, `_print_diff`, `_now_iso`, `_get_cache_path`, `_get_version`, `_is_excluded` (kept/reused for exclude matching).

- [ ] **Step 1: rules.yaml — expand the `filter:` block.** Replace the current `filter:` section with:

```yaml
# Per-provider curation applied during `models refresh` (keyless OpenRouter source).
# A model is kept iff it matches an `allow` glob AND no `exclude` glob.
# Build reads seed.json (already curated) and is never affected by this block.
filter:
  anthropic:
    allow:
      - "claude-opus-*"
      - "claude-sonnet-*"
      - "claude-haiku-*"
      - "claude-fable-*"
    exclude:
      - "*-fast"
      - "claude-3-*"
      - "claude-opus-4"
  openai:
    allow:
      - "gpt-5*"
    exclude:
      - "*-image*"
      - "*-audio*"
      - "*-codex*"
      - "*-pro"
      - "*-nano"
      - "*-luna*"
      - "*-terra*"
      - "*-sol*"
      - "*-chat*"
      - "*:free"
      - "*oss*"
      - "*-instruct"
      - "gpt-5-mini"
      - "gpt-5"
```

- [ ] **Step 2: Write failing tests** in `tests/unit/commands/test_models_command.py`. Reuse the existing `_FakeResponse` helper. Add a `TestFetchOpenRouter` class with a small fixed OpenRouter-shaped payload:

```python
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

def test_fetch_openrouter_maps_and_curates():
    from agent_notes.commands.models import _fetch_openrouter, _load_rules
    with patch("urllib.request.urlopen", side_effect=lambda *a, **k: _FakeResponse(_OR_PAYLOAD)):
        got = _fetch_openrouter(_load_rules())
    anth_ids = {e["id"] for e in got["anthropic"]}
    oai_ids  = {e["id"] for e in got["openai"]}
    assert anth_ids == {"claude-opus-4-8", "claude-opus-5"}      # dots->dashes; -fast & claude-3 dropped
    assert oai_ids  == {"gpt-5.5", "gpt-5.4-mini"}               # keep dots; -luna & -nano dropped
    assert "google" not in got                                   # non-curated provider ignored
    opus48 = next(e for e in got["anthropic"] if e["id"] == "claude-opus-4-8")
    assert opus48["display_name"] == "Claude Opus 4.8"           # "Anthropic: " prefix stripped
    assert opus48["created_at"] is None
    assert set(got["openai"][0].keys()) == {"id"}                # openai entries are id-only

def test_refresh_fails_loud_on_empty(monkeypatch, tmp_path):
    # OpenRouter returns nothing curated -> refresh must sys.exit(1) (CI guard)
    from agent_notes.commands import models
    monkeypatch.setattr(models, "_fetch_openrouter", lambda rules: {"anthropic": [], "openai": []})
    with pytest.raises(SystemExit) as ei:
        models.refresh()
    assert ei.value.code == 1
```

Also: **delete** `TestFetchAnthropic`, `TestFetchOpenAI`, and `TestRefreshUnconfiguredProvider` (the credentialed paths no longer exist). **Keep** `TestRefreshDryRun`, `TestFreeze`, `TestCatalogLoaderCorruptCache`, `TestBuildNoNetworkCall`. Update `TestRefreshDryRun` to patch `_fetch_openrouter` instead of `urlopen`+credentials.

- [ ] **Step 3: Run tests to verify they fail** (`ImportError: _fetch_openrouter`).

- [ ] **Step 4: Implement.** In `agent_notes/commands/models.py`:

Add the curation helper (keep the existing `_is_excluded`):
```python
def _curated(model_id: str, rules: dict, provider: str) -> bool:
    """True iff model_id matches an allow glob and no exclude glob for provider."""
    pf = rules.get("filter", {}).get(provider, {})
    allow = pf.get("allow", [])
    if allow and not any(fnmatch.fnmatch(model_id, pat) for pat in allow):
        return False
    return not _is_excluded(model_id, rules, provider)
```

Add the keyless fetch:
```python
_OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
_CURATED_PROVIDERS = ("anthropic", "openai")

def _fetch_openrouter(rules: dict, *, url: str = _OPENROUTER_URL) -> dict[str, list[dict]]:
    """Fetch the public OpenRouter model list (no auth) and return curated,
    provider-native seed entries keyed by provider.

    Anthropic ids: strip 'anthropic/', convert dots->dashes, entry carries a
    cleaned display_name and created_at=None. OpenAI ids: strip 'openai/',
    keep dots, entry is id-only. Non-curated prefixes are ignored.
    """
    import urllib.request

    version = _get_version()
    req = urllib.request.Request(url, headers={"User-Agent": f"agent-notes/{version}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    out: dict[str, list[dict]] = {p: [] for p in _CURATED_PROVIDERS}
    for m in data.get("data", []):
        mid = m.get("id", "")
        prov, _, rest = mid.partition("/")
        if prov not in _CURATED_PROVIDERS or not rest:
            continue
        native = rest.replace(".", "-") if prov == "anthropic" else rest
        if not _curated(native, rules, prov):
            continue
        if prov == "anthropic":
            name = m.get("name") or native
            if name.startswith("Anthropic:"):
                name = name[len("Anthropic:"):].strip()
            out["anthropic"].append({"id": native, "display_name": name, "created_at": None})
        else:
            out["openai"].append({"id": native})
    return out
```

Rewrite `refresh` (keyless, fail-loud):
```python
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
```

**Delete** `_fetch_anthropic` and `_fetch_openai` entirely. The `from ..services import credentials` import (inside the old `refresh`) is removed with it. Keep `_is_excluded`, `fnmatch`, `_get_version`.

In `agent_notes/cli.py`: leave the `--provider {anthropic,openai}` and `--dry-run` args and the dispatch unchanged (signature is unchanged). No CLI edit expected; confirm `refresh(provider=..., dry_run=...)` still matches.

- [ ] **Step 5: Run tests + byte-identity + suite.**
  - `uv run pytest tests/unit/commands/test_models_command.py -v` → PASS.
  - `uv run pytest tests/` → PASS (no net coverage loss).
  - `scripts/dev/verify_dist_equiv.sh <develop-tip-sha>` → **BYTE-IDENTICAL** (seed.json untouched; rules `filter` is refresh-only).

- [ ] **Step 6: Commit** — `#40 feat(models): keyless OpenRouter source for catalog refresh` (adjust ticket if a dedicated issue exists; else omit `#40`).

---

### Task B: `scripts/dev/update-models` wrapper

**Files:** Create `scripts/dev/update-models` (executable). Mirrors `scripts/dev/install-local`.

- [ ] **Step 1: Write the script.**
```bash
#!/usr/bin/env bash
# Refresh the model catalog from OpenRouter (keyless) and freeze it into
# agent_notes/data/catalog/seed.json. Runs the CLI from the WORKING-TREE
# source (uv run / .venv), never the pipx binary, so `freeze` writes THIS repo.
#
# Usage:
#   scripts/dev/update-models                  # refresh + freeze
#   scripts/dev/update-models --dry-run        # preview only, writes nothing
#   scripts/dev/update-models --provider openai
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

if command -v uv &> /dev/null; then
  uv sync --quiet
  PY_MOD() { uv run python -m "$@"; }
elif [[ -x ".venv/bin/python" ]]; then
  PY_MOD() { .venv/bin/python -m "$@"; }
else
  echo "Error: need uv (brew install uv) or a .venv to run the refresh." >&2
  exit 1
fi

echo "==> Refreshing model catalog from OpenRouter (no credentials needed)"
PY_MOD agent_notes models refresh "$@"

for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    echo "==> Dry run — seed.json left unchanged."
    exit 0
  fi
done

echo "==> Freezing cache into agent_notes/data/catalog/seed.json"
PY_MOD agent_notes models freeze
echo
echo "==> Done. Next steps:"
echo "    git diff agent_notes/data/catalog/seed.json   # review the change"
echo "    uv run pytest tests/ -q"
echo "    git add agent_notes/data/catalog/seed.json && git commit"
```

- [ ] **Step 2: `chmod +x` and verify** `scripts/dev/update-models --dry-run` prints the curated diff (expect `+ anthropic/claude-opus-5`, `+ openai/gpt-5.1`, `+ openai/gpt-5.2`) and leaves `git status` clean (seed.json unchanged).

- [ ] **Step 3: Commit** — `chore(dev): add keyless model-catalog update script`.

---

### Task C: Scheduled auto-PR workflow

**Files:** Create `.github/workflows/update-models.yml`.

- [ ] **Step 1: Write the workflow.**
```yaml
name: Update model catalog
on:
  schedule:
    - cron: "0 6 * * 1"   # Mondays 06:00 UTC
  workflow_dispatch: {}

permissions:
  contents: write
  pull-requests: write

jobs:
  update-models:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: develop

      - uses: astral-sh/setup-uv@v6

      - name: Sync deps
        run: uv sync

      - name: Refresh + freeze catalog (keyless via OpenRouter)
        run: |
          uv run python -m agent_notes models refresh
          uv run python -m agent_notes models freeze

      - name: Detect model add/remove vs committed seed
        id: diff
        # PR only when the SET of model ids changed (added or removed).
        # Immune to the fetched_at timestamp, entry reordering, and cosmetic
        # field churn (display_name) — those must NOT open a PR.
        run: |
          seed=agent_notes/data/catalog/seed.json
          ids() { python3 -c 'import json,sys;d=json.load(sys.stdin);print(chr(10).join(sorted(i["id"] for p in d["providers"].values() for i in p)))'; }
          old="$(git show HEAD:"$seed" | ids)"
          new="$(ids < "$seed")"
          if [ "$old" = "$new" ]; then
            echo "changed=false" >> "$GITHUB_OUTPUT"
            git checkout -- "$seed"            # no model change -> discard timestamp/format churn
          else
            echo "changed=true" >> "$GITHUB_OUTPUT"
            echo "Model set changed:"; diff <(printf '%s' "$old") <(printf '%s' "$new") || true
          fi

      - name: Run test suite (guard before opening PR)
        if: steps.diff.outputs.changed == 'true'
        run: uv run pytest tests/ -q

      - name: Open / update PR (gh CLI — no third-party action)
        if: steps.diff.outputs.changed == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git checkout -B automation/model-catalog-update
          git add agent_notes/data/catalog/seed.json
          git commit -m "chore(catalog): refresh model catalog from OpenRouter"
          git push -f origin automation/model-catalog-update
          gh pr create --base develop --head automation/model-catalog-update \
            --title "chore(catalog): model catalog update" \
            --body "Automated refresh from OpenRouter (keyless). Review the seed.json diff before merging; add pricing/rules for any new model." \
            || gh pr edit automation/model-catalog-update --base develop
```

**Devops notes:**
- **No third-party actions.** PR creation uses the GitHub-native `gh` CLI (pre-installed on `ubuntu-latest`) + `git`, authenticated with the built-in `${{ github.token }}`. Only first-party actions remain: `actions/checkout` and `astral-sh/setup-uv`.
- `gh pr create` fails if a PR for the branch already exists; the `|| gh pr edit …` fallback keeps a single long-lived PR (the force-push updates its contents).
- No secrets referenced anywhere (that is the whole point).
- Known limitation to leave as-is: a PR opened with the default `GITHUB_TOKEN` does **not** trigger the `validate.yml` `pull_request` CI — the in-job `pytest` step is the compensating guard. A PAT to re-enable PR CI is an optional future enhancement, out of scope.
- The change gate is a semantic id-set comparison via `python3` (present on ubuntu-latest), verified to fire only on add/remove — not on timestamp, reordering, or `display_name` churn.

- [ ] **Step 2: Static-validate** the YAML (`actionlint` if available; otherwise a YAML parse). End-to-end CI run is **not** verifiable locally — it requires the workflow on GitHub and a `workflow_dispatch` trigger (the user's action).

- [ ] **Step 3: Commit** — `ci: add scheduled keyless model-catalog auto-PR`.

---

## Self-Review

**1. Spec coverage.** OpenRouter keyless source (Task A), curation policy locked in `rules.yaml` (Task A step 1), dev script (Task B), scheduled auto-PR gated on real change (Task C). Credentials fully removed from the refresh path. Build byte-identical (filter is refresh-only; seed.json untouched).

**2. Placeholder scan.** No third-party action placeholders remain — PR creation is `gh` CLI + `git`, no pinning needed. `<develop-tip-sha>` in Task A step 5 is the byte-identity baseline the executor fills from `git rev-parse develop`.

**3. Type consistency.** `_fetch_openrouter -> dict[str, list[dict]]`; `refresh` consumes it and merges into `{"fetched_at", "providers"}` exactly as before. `_curated`/`_is_excluded` both take `(model_id, rules, provider)`. Entry dicts match the current seed schema per provider.

**Risk notes.**
- **First real refresh reshapes seed.json** (adds `claude-opus-5`, `gpt-5.1`, `gpt-5.2`; anthropic `created_at` normalizes to null; openai entries become id-only). That data change is produced by running the tool and is reviewed as its own PR — it may require updating model-pinned tests (e.g. "newest opus"), which is **out of scope for the mechanism** and handled when that PR is raised.
- **OpenRouter as third-party source of truth** — could lag a release or change schema; the human-reviewed PR is the backstop.
- **Glob drift** (e.g. a future `gpt-5.6` shipping only as `-luna/terra/sol`) surfaces in the PR diff for a human to resolve.

## Execution Handoff

Executing **subagent-driven**: Task A → `coder` (TDD), then `reviewer` + `security-auditor` (verify no credential use, keyless assumption, network-fetch safety). Tasks B + C in parallel after A → `coder` (B) and `devops` (C), then `security-auditor` on C (permissions scope, no-secret confirm, first-party-only actions). Lead verifies byte-identity + suite + the `--dry-run` curated diff after each.
