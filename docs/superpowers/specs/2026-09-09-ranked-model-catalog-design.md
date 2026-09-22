# Ranked Model Catalog — Design Spec

## Problem

Today model selection is: role declares `typical_class` (fable/opus/sonnet/haiku, assigned by hand-written globs in `agent_notes/data/catalog/rules.yaml:6-13`), resolver picks the newest non-deprecated model of that class (`agent_notes/services/model_resolver.py:144-190`), "newest" = natural version sort (`agent_notes/registries/model_registry.py:18`, correct — handles `4-10 > 4-9`).

- **Gap 1:** no cross-class or cross-provider ranking. "Opus outranks Sonnet" exists nowhere in data.
- **Gap 2:** "newest = best" is an assumption. A newer but weaker model auto-wins its class.
- **Gap 3 (FIXED):** curation globs in `rules.yaml:70-87` were version-pinned. `allow: ["gpt-5*"]` could not match `gpt-6-astra` (released 2026-09-04, coding index 76.9), and excludes on `*-sol*`, `*-terra*`, `*-luna*` dropped `gpt-5.6-sol` (77.4), `gpt-5.6-terra` (76.7), `gpt-5.6-luna` (71.4, $0.20/M). Shipped fix: `openai.allow: ["gpt-*"]` with excludes narrowed to `gpt-3.5*`, `gpt-4*`, and non-chat/non-text variants (image, audio, codex, pro, chat, free, oss, instruct, preview). OpenAI's curated set grew from 5 to 13 models.

## Rejected approach: price-derived rank

Verified anti-correlated with capability, because prices fall as models improve. Evidence: `gpt-4` (2023) $30/M in vs `gpt-5.5` $5/M (coding 13.1 vs 74.9); `claude-opus-4.1` $15 vs `claude-opus-5` $5; `claude-fable-5.1` $10 vs `claude-opus-5` $5. A price rank would promote old/deprecated models to the lead agent.

## Data source

OpenRouter `https://openrouter.ai/api/v1/models` (keyless, public) publishes `benchmarks.artificial_analysis.{intelligence_index, coding_index, agentic_index}` and `benchmarks.design_arena` (elo/rank), plus `pricing.{prompt,completion}`, `context_length`, `created`, and `reasoning.{supported_efforts, default_effort}`. Coverage: 84/120 anthropic+openai entries have non-empty benchmarks; for curated non-`:batch` entries, anthropic 10/15 rated, openai 22/60 rated.

## Design

### 1. Two ranked lists — SHIPPED

`seed.json` keeps `providers.anthropic` / `providers.openai`; each list is ordered frontier→lowest by `coding_index`, with unrated (`coding_index: null`) entries sorted last. Each entry carries `rank` (1-based), `coding_index`, `price_in`, `price_out`, `context_length`, `created_at`. Prices are USD per 1M tokens, rounded to 6 decimal places (`agent_notes/commands/models.py:90`). Rank is computed at refresh time and frozen into the file so ordering is reviewable in the PR diff, not recomputed at load.

### 2. Selection: per-role budget ceiling — SHIPPED

Each role in `agent_notes/data/roles/*.yaml` carries `budget` (max USD per 1M input tokens): orchestrator `null` (unbounded), reasoner `5.0`, worker `2.0`, scout `1.0`. Selection lives in `select_model_for_role(models, role, backend)` (`agent_notes/services/model_resolver.py`) — the single implementation of "which model does this role get"; both Branch 3 of `ModelResolver.resolve()` and the install wizard's `_default_model_for_role` call it, so they can never disagree. It walks the catalog in rank order (frontier first) and returns the first model that is (a) rated (`coding_index is not None`), (b) within budget (`price_in <= role.budget`, unbounded when `budget` is `null`), and (c) servable by the backend. `backend.preferred_family` and non-deprecated status are applied as a widening ladder (preferred family + non-deprecated → any family + non-deprecated → preferred family + deprecated → any + deprecated) rather than hard filters. This replaces `typical_class` matching and newest-wins entirely.

VERIFIED resulting defaults: on the `claude` backend, orchestrator → `claude-fable-5-1` (renders `fable`), reasoner → `claude-opus-5` (`opus`), worker → `claude-sonnet-5` (`sonnet`), scout → `claude-haiku-4-5` (`haiku`). On the `codex` backend, orchestrator/reasoner/worker → `gpt-5.6-sol`, scout → `gpt-5.6-luna`.

Accepted consequence: on OpenAI, orchestrator/reasoner/worker all resolve to `gpt-5.6-sol` because the top-ranked model is inside the worker budget. Tier distinction disappears on that provider. Accepted; a separate mechanism would be needed to force distinction.

### 3. No veto mechanism — decision and consequence

The human-veto flag that used to bar a model from automatic selection was deleted entirely: the flag itself, its `rules.yaml` key, the domain field, all filters that read it, and its tests. There is no gate on automatic selection anywhere in the codebase anymore.

Consequence: ranking is unmediated. Benchmarks rank `claude-fable-5-1` (coding 81.6) above `claude-opus-5` (78.0), so Fable is rank 1 for Anthropic and becomes the orchestrator default (unbounded budget takes the top-ranked rated model). There is no mechanism left to bar a model from automatic selection — a model that ranks first is selected first, regardless of any other property.

### 4. Wizard — SHIPPED (reduced column set)

Per role, the wizard renders the provider's full compatible-model list, pre-selecting the budget pick via `_default_model_for_role` (section 2). Shipped columns are model id, coding index, and `$/M in` (`MODEL_COLUMNS_HEADER`, shared with `config role-model`); the list order is the catalog rank order, but no separate rank-number, price-out, or context-length columns are rendered. Unrated models sort below the ranked block — manually selectable, never auto-selected. The original proposal also called for visibly barring vetoed entries; that veto mechanism no longer exists — see section 3.

### 5. Diff view — one function, three surfaces — NOT IMPLEMENTED

Specced only; no code exists for this on any surface (see "Not yet implemented" below). Design as originally proposed:

Pure function `(role, current_model, catalog) -> (candidate, delta_coding, delta_price_in)`.

- **Wizard:** mark current and best-in-budget inline with delta on the candidate row.
- **Refresh PR body:** emit the table whenever a rank change moves a role's resolved default, e.g. "worker: sonnet-5 → gpt-5.6-sol, +6.3 coding, -20% $/M in".
- **`agent-notes config show`:** optional drift column. Flag as optional — it turns a state dump into an advisory surface.

Constraints: label the cost column `$/M in` explicitly, since output prices do not move proportionally (sonnet-5 $2/$10 vs fable-5 $10/$50) and a blended claim would mislead. Against an unrated pin, show `—` for coding delta, never a number.

### 6. CLI numeric selector — SHIPPED

`agent-notes config role-model <role> <n>` accepts `<n>` as a 1-based index into the same rank-ordered, servable-for-this-backend list the wizard shows (`compatible_models_for(backend)` in `agent_notes/commands/config.py`). `agent-notes config role-model <role>` with no value prints that numbered list (columns: `#  model  coding  $/M in`, unrated shown as `—`). A bare integer (`\d+`) is resolved as an index; any other token is still parsed as a model id (backward compatible). The resolved id is echoed (`N -> model_id`) before the change is applied, and `_apply_and_regenerate` shows a diff and prompts for confirmation before writing. With `--cli both` (or no `--cli`, when multiple CLIs are installed) an index is ambiguous across backends — `_resolve_index` exits with an error unless exactly one target CLI is selected.

### 7. Refresh pipeline

`_fetch_openrouter` (`agent_notes/commands/models.py:64-99`) gains benchmark/pricing enrichment; the existing `created_at=None` placeholder is filled. Re-sort by coding_index. The weekly workflow (`.github/workflows/update-models.yml`) additionally reports role-default changes in the PR body.

## Error handling

- Missing `coding_index` → unrated, never auto-selected. A `0.0` score is real data, not absence — must not collapse (verified: `gpt-5.4` reports intelligence_index 0.0 but coding_index 71.1).
- Empty eligible set for a budget → hard error naming role and ceiling. Never silently substitute across tiers.
- Benchmarks absent from the API response entirely → keep the previous ranking rather than flattening.

## Testing

Ranking is a pure function of the fetched payload; test offline against a fixture. Cases: rank ordering, budget selection per role, unrated exclusion, 0.0-vs-missing distinction, and a regression fixture asserting today's four Anthropic defaults do not move.

## Out of scope

- Rendering is unchanged. Claude keeps `use_model_class: true` (`agent_notes/data/cli/claude.yaml:31`) and keeps writing `model: sonnet` into agent frontmatter (via `rules.yaml: classes`, now a rendering mapping only — it plays no part in selection). Changing this would version-pin every existing user's agents.
- `deprecated` semantics unchanged.
- State pins (resolver Branch 1) continue to bypass all of this.

## Not yet implemented

- **Diff view (section 5):** the pure `(role, current_model, catalog) -> (candidate, delta_coding, delta_price_in)` function is specced but not built on any of the three proposed surfaces — wizard, refresh PR body, or `config show`.
- **`agent-notes config show` drift column:** `show()` (`agent_notes/commands/config.py`) prints the currently assigned role→model per CLI; it has no column comparing the assignment against the current rank/budget pick.
