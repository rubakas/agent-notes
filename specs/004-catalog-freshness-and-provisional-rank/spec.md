# 004 — Catalog Freshness and Provisional Rank

**Feature Branch**: `fix/catalog-freshness-and-provisional-rank`

**Created**: 2026-10-02

**Status**: Implemented 2026-10-02

**Input**: User description: "during install the models list is not updated, i don't see opus 5.5. also update the default map of role models"

## Investigation

Two independent root causes, both reproduced on 2026-10-02 against the installed 2.35.0.

**RC1 — a stale XDG cache shadows every newer bundled catalog.** `catalog_loader._load_seed` (`agent_notes/registries/catalog_loader.py:28-42`) returns `~/.cache/agent-notes/catalog.json` whenever it exists and parses, with no freshness check. That cache is written by `models refresh` and nothing ever expires it. On this machine it was written by a refresh on 2026-09-09 (`fetched_at: 2026-09-09T21:37:09Z`, 13 Anthropic models), while 2.35.0 ships a seed fetched 2026-10-01 with 15 (adds `claude-opus-5-5`, `claude-sonnet-5-5`). Every catalog-reading surface inherits the stale view: the install wizard, `config role-model`, `list models`, and budget+rank resolution at build time.

Reproduction:

```
$ agent-notes list models                         # stale cache present
  anthropic (13): ... no claude-opus-5-5
$ XDG_CACHE_HOME=$(mktemp -d) agent-notes list models
  ... 14  claude-opus-5-5     57.6   —   4.00
      15  claude-sonnet-5-5   56.0   —   2.00
```

Every user who has ever run `models refresh` is affected; a package upgrade alone can never deliver new models to them. `models.py::_load_current_catalog` (`agent_notes/commands/models.py:181-194`) duplicates the same unconditional cache precedence, and `models.py::_get_cache_path` duplicates `catalog_loader._get_cache_path`.

**RC2 — new models cannot become role defaults while unrated.** Role defaults are not a stored map. They are computed by `select_model_for_role` (`agent_notes/services/model_resolver.py:44`), which walks the catalog frontier-first by `coding_index` and skips any model whose `coding_index is None`. `claude-opus-5-5` and `claude-sonnet-5-5` carry `coding_index: null` — OpenRouter's Artificial Analysis block publishes only an intelligence index for them (re-checked live on 2026-10-02: `coding_index=None`, `intelligence_index` 57.6 / 56.0). So even with RC1 fixed, the defaults stay `fable-5-1 / opus-5 / sonnet-5 / haiku-4-5`, and will stay there until upstream publishes a coding score on its own schedule.

Prices are not the blocker: both match Anthropic's published rates (Opus 5.5 $4/$20, Sonnet 5.5 $2/$10), both are already in `pricing.yaml`, and both fit their roles' budgets (reasoner $5.0, worker $2.0).

**Decision (owner, 2026-10-02):** move the defaults with a hand-curated *provisional* coding score in `rules.yaml`, consulted only while upstream has none. Chosen over static per-role default pins (reintroduces the fixed map the ranked catalog replaced, stale on every release) and over fixing the list only (no default change until upstream rates).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrading the package delivers its new models (Priority: P1)

A user who once ran `models refresh` upgrades agent-notes and runs the install wizard. The model list shows every model the new package ships, including ones released after their last refresh.

**Why this priority**: P1 — it is the reported bug, it affects every surface that reads the catalog, and without it Story 2 is invisible to anyone with a cache.

**Independent Test**: With the 2026-09-09 cache in place, `agent-notes list models` lists `claude-opus-5-5` and `claude-sonnet-5-5`.

**Acceptance Scenarios**:

1. **Given** a cache whose `fetched_at` is older than the bundled seed's, **When** the catalog loads, **Then** the bundled seed is used.
2. **Given** a cache whose `fetched_at` is newer than or equal to the seed's (a fresh `models refresh`), **When** the catalog loads, **Then** the cache is used — a user refreshing ahead of a release still sees the newer list.
3. **Given** `models refresh --provider openai` run against a stale cache, **When** it merges, **Then** the untouched `anthropic` block comes from the newer of cache and seed, not from the stale cache.

### User Story 2 - New models become the recommended defaults (Priority: P2)

A user runs the install wizard and accepts the recommended models. Reasoner and worker are pre-selected as `claude-opus-5-5` and `claude-sonnet-5-5`.

**Why this priority**: P2 — the owner's explicit request; depends on Story 1 to be visible to users with a cache.

**Independent Test**: The budget+rank selection, for each backend and role, returns the table under SC-002.

**Acceptance Scenarios**:

1. **Given** `claude-opus-5-5` is unrated upstream and has a provisional score of 78.1 in `rules.yaml`, **When** the reasoner default is selected for `claude`, **Then** it is `claude-opus-5-5`.
2. **Given** upstream later publishes a real `coding_index` for `claude-opus-5-5`, **When** the catalog loads, **Then** the real score is used and the provisional one is ignored, with no edit to `rules.yaml`.
3. **Given** a model with a provisional score, **When** any model table is printed, **Then** its coding column reads `78.1*`, so a provisional number is never presented as a benchmark result.

### Edge Cases

- Cache has no `fetched_at`: treat as older than the seed (the shipped data wins). Every cache `models refresh` writes carries one, so this only covers hand-made or truncated files.
- Corrupt cache: unchanged — warn and fall back to the seed.
- Explicit `catalog_dir`: unchanged — the cache is never consulted.
- Provisional entry for a model upstream already rates: ignored (auto-retired). The entry is dead config; removing it is a follow-up cleanup, never a failing test — a test that trips when upstream rates a model would abort the weekly refresh workflow, which already fails silently (see the 2026-10-01 note in the catalog refresh history).
- Provisional entry naming an id not in the catalog: a typo. Caught by a test.
- Capability-band tests in `test_catalog_class_tiers.py` derive their bounds from Claude models' coding scores. Provisional scores must not feed those bounds: they are curated guesses, and a bound derived from a guess cannot catch a misclassification.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `catalog_loader._load_seed` MUST return the cache only when its `fetched_at` is greater than or equal to the bundled seed's `fetched_at` (ISO-8601 UTC `Z` strings compare correctly as text). A cache without `fetched_at` MUST lose to the seed.
- **FR-002**: `models.py::_load_current_catalog` and `models.py::_get_cache_path` MUST be deleted and their callers routed through `catalog_loader`'s implementations, so there is one cache-precedence rule.
- **FR-003**: `rules.yaml` MUST gain a top-level `provisional_coding_index:` block, indexed by normalized registry id, each entry commented with the reason and the date checked. Initial entries: `claude-opus-5-5: 78.1` (just above `claude-opus-5` at 78.0, below `claude-fable-5-1` at 81.6) and `claude-sonnet-5-5: 71.6` (just above `claude-sonnet-5` at 71.5).
- **FR-004**: `Model` MUST carry the provisional value in its own field (`provisional_coding_index`), leaving `coding_index` as the upstream benchmark value only. A `rank_score` property returns `coding_index` when set, else `provisional_coding_index`.
- **FR-005**: Ranking (`model_registry._frontier_key`) and eligibility (`model_resolver.select_model_for_role._eligible`) MUST use `rank_score`. No other consumer changes its reading of `coding_index`.
- **FR-006**: `model_columns` MUST print a provisional score with a trailing `*` (`78.1*`). `list models` MUST print a one-line legend when any listed model shows one.
- **FR-007**: `tests/unit/test_cache_isolation.py` MUST plant its probe with a `fetched_at` in the far future. Its current `2020-01-01` probe would lose to the seed under FR-001 even with isolation broken, so the test could no longer fail.
- **FR-008**: `docs/ADD_MODEL.md` MUST document `provisional_coding_index` next to `price_overrides`, and correct its statement that the cache shadows the bundled seed (line 69).
- **FR-009**: `CHANGELOG.md` `[Unreleased]` MUST record both changes, including that an existing install keeps its saved role pins until the wizard is re-run.

### Non-Goals

- Provisional scores for the unrated GPT-6 models (`gpt-6-sol`, `gpt-6-1-sol`, `gpt-6-luna`). The mechanism supports them; choosing the numbers is a separate call.
- `list models` ordering. It sorts by the seed's per-provider `rank`, which is upstream's; a provisional model keeps its upstream position there.
- Merging a user's `~/.config/agent-notes/models.yaml` `provisional_coding_index` block. `_merge_rules` drops unknown keys today; extending it is not needed for this request.
- Migrating role pins already saved in existing installs' `state.json`. Re-running the wizard re-pins to the new defaults; rewriting users' explicit choices silently is not this change's call.
- The isolation test still writes to the real `~/.cache` (it snapshots and restores). Pre-existing; out of scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the 2026-09-09 cache left in place, `uv run agent-notes list models` lists 15 Anthropic models including `claude-opus-5-5` and `claude-sonnet-5-5`.
- **SC-002**: Budget+rank defaults change exactly as simulated on 2026-10-02 against the bundled seed, and nowhere else:

  | backend | orchestrator | reasoner | worker | scout |
  |---|---|---|---|---|
  | claude | claude-fable-5-1 | claude-opus-5 → **claude-opus-5-5** | claude-sonnet-5 → **claude-sonnet-5-5** | claude-haiku-4-5 |
  | opencode | claude-fable-5-1 | claude-opus-5 → **claude-opus-5-5** | claude-sonnet-5 → **claude-sonnet-5-5** | claude-haiku-4-5 |
  | codex | gpt-5-6-sol | gpt-5-6-sol | gpt-5-6-terra | gpt-5-6-luna |

- **SC-003**: Each new test fails when its production change is reverted (mutation check): the freshness comparison, the `rank_score` use in `_frontier_key` and in `_eligible`, and the `*` marker.
- **SC-004**: `uv run pytest -q` is green.
- **SC-005**: In a sandboxed wizard run (fake `HOME`, empty `XDG_CACHE_HOME`, accept-all), the saved state pins `reasoner: claude-opus-5-5` and `worker: claude-sonnet-5-5` for `claude`, and the rendered `~/.claude/agents/architect.md` (the only reasoner agent) carries `model: claude-opus-5-5` and `coder.md` (worker) carries `model: claude-sonnet-5-5`.

## Assumptions

- `fetched_at` is always written by `models refresh` as `%Y-%m-%dT%H:%M:%SZ` (`_now_iso`), so text comparison orders correctly.
- An unpinned `agent-notes build` on `claude` renders the class (`use_model_class: true`), so SC-002's change shows up in rendered Claude files through the wizard's saved pins, not through an unpinned build — where both before and after read `opus` / `sonnet`.
- `lead` (orchestrator) is excluded from Claude Code rendering, so the orchestrator column has no effect there.

## Verification

Measured 2026-10-02 on branch `fix/catalog-freshness-and-provisional-rank`, from the working tree (`uv run` / `.venv/bin/agent-notes`), never the pipx binary.

**SC-001 — met.** With the real 2026-09-09 cache left in place (its sha1 `21125e88…` unchanged before and after), `uv run agent-notes list models` lists `anthropic (15)`, including `claude-opus-5-5 57.6 78.1* 4.00` and `claude-sonnet-5-5 56.0 71.6* 2.00`. The installed 2.35.0 binary still prints `anthropic (13)` against the same cache.

**SC-002 — met.** `TestRealRegistryResolution` pins the table for `claude`, `codex` and `opencode` (opencode newly added), through both the resolver and the wizard's pre-selection. Nothing else in the default map moved.

**SC-003 — met.** Each guard was reverted and its test watched fail, then restored:

| Production change reverted | Failing test(s) |
|---|---|
| freshness comparison replaced by `True` (cache always wins) | 3 of `TestCatalogFreshness` |
| `>=` tightened to `>` | `test_cache_as_new_as_seed_is_used` |
| `_frontier_key` back to `coding_index` | `test_provisional_score_ranks_ahead_of_a_lower_rated_model` |
| `_eligible` back to `coding_index` | `test_provisional_score_makes_an_unrated_sole_candidate_selectable` |
| `*` dropped from the provisional format | `test_provisional_score_is_marked_and_explained` |
| typo'd id (`claude-sonet-5-5`) added to the block | `test_every_provisional_score_names_a_catalog_model` |
| conftest's `XDG_CACHE_HOME` isolation removed | `test_real_home_cache_is_not_read` — which PASSED under the same mutation before FR-007's probe-date change, confirming the probe had become unfalsifiable |

**SC-004 — met.** `uv run pytest -q`: 2241 passed, 15 deselected (baseline 2227; +14 new tests).

**SC-005 — met.** Accept-all install with fake `HOME`/`XDG_CONFIG_HOME`/`XDG_CACHE_HOME`, the fake cache seeded with a copy of the stale 2026-09-09 catalog, defaults fed as Enter keypresses. Wizard printed `Reasoner: claude-opus-5-5 … 78.1*` and `Worker: claude-sonnet-5-5 … 71.6*`; saved state `role_models = {reasoner: claude-opus-5-5, worker: claude-sonnet-5-5, scout: claude-haiku-4-5}`; rendered `architect.md` → `model: claude-opus-5-5`, `coder.md` → `model: claude-sonnet-5-5`. Real `~/.config/agent-notes/state.json`, `~/.claude/agents` and `~/.cache/agent-notes/catalog.json` checksums identical before and after. Symlink mode pointed the sandbox's agents into this repo's git-ignored `agent_notes/dist/`, which the run rebuilt; no real install links there.

**Test changes beyond the new tests** — each follows FR-005 moving the ordering key from `coding_index` to `rank_score`, none relaxes an assertion:

- `test_config_role_model_index.py::test_list_shows_rank_order…`, `::test_merged_list_is_globally_frontier_first` and `test_registries.py::test_every_role_resolves…` assert their frontier-first / rated invariants on `rank_score`.
- `test_catalog_equivalence.py::test_registry_all_preserves_catalog_rank_order` leaves provisionally-ranked models out of the per-provider position check (the seed's rank is upstream's); where they land is pinned by the resolver tests above.
- `test_list_command.py::test_missing_metrics_render_an_em_dash` and `test_config_role_model_index.py::test_unrated_models_render_a_dash` select models with no score at all (`rank_score is None`); their old "first null `coding_index`" pick became `claude-opus-5-5`, which now prints `78.1*`.
- `test_models_command.py::test_dry_run_writes_no_files` patches `models._load_seed` in place of the deleted `_load_current_catalog`.

**Follow-ups, not done:** the installed CLI is still 2.35.0 — the fix reaches it only after release and a clean reinstall. Re-run `agent-notes install` (or `--local --reconfigure`) in existing installs to move their saved pins. The wizard and `config role-model` show the `*` without the legend that `list models` prints.
