# 004 — Catalog Freshness and Provisional Rank: Tasks

Tickets derived from `spec.md`. Each is test-first: write the failing test, watch it fail for the stated reason, then change production code.

## Group 1 — Catalog freshness (Story 1)

### T01: Newer of cache and seed wins
Blocked by: None
Files: `agent_notes/registries/catalog_loader.py`, `tests/unit/commands/test_models_command.py` (`TestCatalogLoaderCorruptCache`)
Change: In `_load_seed`, read the seed, then use the cache only if its `fetched_at` >= the seed's; a cache with no `fetched_at` loses. Corrupt-cache warning path unchanged. Update the `load_catalog` docstring.
Tests: stale cache (fetched_at 2020) → seed models returned, cache's model absent; cache with equal fetched_at → cache used; cache with no fetched_at → seed used. Existing 2099-dated tests stay green unchanged.
Done when: FR-001 tests pass, and fail when the comparison is removed.

### T02: One cache-precedence rule
Blocked by: T01
Files: `agent_notes/commands/models.py`, `tests/unit/commands/test_models_command.py`
Change: Delete `models._get_cache_path` and `models._load_current_catalog`; `refresh` and `freeze` use `catalog_loader._get_cache_path` and `catalog_loader._load_seed(seed_path, use_cache=True)`. Re-point the tests that patch `models._load_current_catalog`.
Tests: `refresh --provider openai` over a stale cache keeps the bundled seed's `anthropic` block (Story 1, scenario 3).
Done when: FR-002; `grep -n "_load_current_catalog\|def _get_cache_path" agent_notes/commands/models.py` is empty.

### T03: Keep the isolation probe falsifiable
Blocked by: T01
Files: `tests/unit/test_cache_isolation.py`
Change: Probe `fetched_at` → `2999-01-01T00:00:00Z`, with a comment saying why.
Done when: FR-007; with `pytest_configure`'s `XDG_CACHE_HOME` line temporarily removed, the test fails.

## Group 2 — Provisional rank (Story 2)

### T04: `provisional_coding_index` on Model and in the loader
Blocked by: None
Files: `agent_notes/domain/model.py`, `agent_notes/registries/catalog_loader.py`, `tests/unit/registries/test_catalog_equivalence.py`
Change: Add `provisional_coding_index: Optional[float] = None` and a `rank_score` property (`coding_index` if not None, else provisional). Loader reads `rules.get("provisional_coding_index") or {}` and sets the field.
Tests: (a) unrated seed entry + provisional → `rank_score` is the provisional value, `coding_index` stays None; (b) rated seed entry + provisional → `rank_score` is the real value (auto-retire); (c) every id in the shipped `provisional_coding_index` block exists in the catalog (typo guard).
Done when: FR-004.

### T05: Rank and select by `rank_score`
Blocked by: T04
Files: `agent_notes/registries/model_registry.py` (`_frontier_key`), `agent_notes/services/model_resolver.py` (`_eligible`, docstrings), `tests/unit/services/test_model_resolver_characterization.py` (or nearest resolver test)
Change: `_frontier_key` and `_eligible` read `rank_score` instead of `coding_index`.
Tests: fixture catalog where an unrated model with a provisional score above a rated one is selected for a role whose budget admits both; it is not selected without the provisional score.
Done when: FR-005; both new tests fail when either call site is reverted to `coding_index`.

### T06: Ship the two provisional scores
Blocked by: T05
Files: `agent_notes/data/catalog/rules.yaml`, tests pinning today's claude/opencode reasoner and worker defaults (found via `grep -rln 'claude-opus-5"\|claude-sonnet-5"' tests`)
Change: Add the `provisional_coding_index` block with `claude-opus-5-5: 78.1` and `claude-sonnet-5-5: 71.6`, each with a comment citing the 2026-10-02 OpenRouter check and the owner decision. Update only those test expectations that assert the *default* for reasoner/worker; leave tests that pin a model explicitly alone.
Tests: one test asserting the SC-002 table for all three backends.
Done when: FR-003, SC-002. `UNRATED_BY_DECISION` keeps both entries — they are still unrated upstream — and the capability-band bounds are unchanged, because `_claude()` reads `coding_index`, not `rank_score`.

### T07: Mark provisional scores in model tables
Blocked by: T04
Files: `agent_notes/commands/config.py` (`model_columns`), `agent_notes/commands/list.py`, `tests/unit/commands/test_list_command.py`
Change: Coding column prints `f"{p:.1f}*"` when only a provisional score exists. `list models` prints `  * provisional score — not yet rated upstream` once, after the table, when any row has one.
Done when: FR-006; column alignment unchanged (`78.1*` is five characters in a six-character column).

## Group 3 — Docs and verification

### T08: Docs and changelog
Blocked by: T06, T07
Files: `docs/ADD_MODEL.md`, `CHANGELOG.md`
Change: Document `provisional_coding_index` beside `price_overrides`; fix the line-69 claim that the cache shadows the seed. CHANGELOG `[Unreleased]`: a Fixed entry (stale cache) and a Changed entry (new reasoner/worker defaults; existing installs keep saved pins until the wizard is re-run).
Done when: FR-008, FR-009.

### T09: End-to-end verification
Blocked by: T01–T08
Change: Full suite; mutation checks per SC-003; `uv run agent-notes list models` with the real stale cache (SC-001); a sandboxed accept-all wizard run (fake `HOME`, empty `XDG_CACHE_HOME`, pexpect) checking the saved pins and the rendered `architect.md` / `coder.md` frontmatter (SC-005).
Done when: SC-001 – SC-005 recorded in a `## Verification` section of `spec.md`.
