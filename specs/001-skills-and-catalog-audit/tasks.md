# 001 — Skills and Catalog Audit: Tasks

Tracer-bullet tickets derived from `spec.md`. Every ticket cites the finding(s) it implements. No invented work.

## Group 1 — Money (B)

### T01: Fix `claude-sonnet-5` price in pricing.yaml
Blocked by: None
Files: `agent_notes/data/pricing.yaml:21-24`
Change: Replace the Sonnet 4.6 rate `{in: 3.00, out: 15.00}` with `{in: 2.00, out: 10.00, cache_read: 0.20, cache_write_5m: 2.50, cache_write_1h: 4.00}`, matching `seed.json.price_in/price_out` for `claude-sonnet-5` and the file's own 0.1x/1.25x/2x cache ratios. Update `updated_at`.
Done when: Cost report for `claude-sonnet-5` matches `seed.json` price_in/price_out to the cent; `worker` role no longer bills above its 2.0 budget gate for this model (B1).

### T02: Fix OpenAI catalog pricing glob (13 models flat-priced)
Blocked by: None
Files: `agent_notes/data/pricing.yaml:57-59`
Change: Replace the single `gpt-*`/`o1*`/`o3*`/`o4*` glob at flat 2.50/10.00 with per-model or per-tier entries covering all 13 catalog OpenAI ids, sourced from the live OpenAI pricing page. Rename the entry off "GPT-4 / o-series" once it covers the current lineup.
Done when: `gpt-5-nano`, `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-luna` (the four ids named in B2) each report their true published price, not the flat 2.50/10.00.

### T03: Verify and fix Fable 5.1 cache-read rate
Blocked by: None
Files: `agent_notes/data/pricing.yaml:17-20`
Change: OPEN/PLAUSIBLE (B3) — first confirm against the live Anthropic pricing page whether Claude Fable 5.1 has a distinct `cache_read` rate ($0.25/MTok per the provider reference cited in B3) versus Fable 5. If confirmed, split the single `*fable*` glob into separate Fable 5 / Fable 5.1 entries. If not confirmed, close this ticket with the verification result recorded and no code change.
Done when: Verification result is recorded (confirmed-and-fixed, or confirmed-not-an-issue) — this ticket must not ship a numeric change without a checked source.

### T04: Reconcile pricing.yaml against seed.json as single price source
Blocked by: maintainer decision (spec.md Decisions #2)
Files: `agent_notes/data/pricing.yaml`, `agent_notes/data/catalog/seed.json`, catalog loading code (`catalog_loader.py`)
Change: Per maintainer decision — either derive `pricing.yaml` from `seed.json.price_in/price_out` at load time, or add an automated test that fails when the two diverge for any model. Do not ship a numbers-only fix; the mechanism that let B1/B2/B3 happen must close (B4).
Done when: Maintainer has chosen an approach; a re-run of the seed.json/pricing.yaml diff finds zero discrepancies, or CI fails on the first future discrepancy.

## Group 2 — Broken gate & dead install path

### T05: Remove `wiki` from VALID_MEMORY_BACKENDS test gate
Blocked by: None
Files: `tests/plugins/test_skills.py:80`
Change: Remove `wiki` from `VALID_MEMORY_BACKENDS`, matching `agent_notes/memory/memory_backend.py:45-50`'s `_REMOVED_BACKENDS = {"wiki"}`.
Done when: A skill declaring `requires_memory: wiki` fails validation instead of silently passing and becoming invisible (D4).

### T06: Stop writing dead `~/.codex/skills/` directory
Blocked by: None (implements default recommendation from spec.md Decisions #3; flag for maintainer confirmation)
Files: `agent_notes/services/install_plan.py:90-92`, `agent_notes/services/install_executor.py:67-76,107-120`
Change: Remove `~/.codex/skills/` as an install target. Codex CLI already receives skills via the `~/.agents/skills/` mirror (A3). Note in the ticket/PR that this changes uninstall behavior for existing installs that already have the dead directory populated.
Done when: A fresh install writes no files to `~/.codex/skills/`; `~/.agents/skills/` install is unaffected (A2).

## Group 3 — Skill content: in-house (D)

### T07: Fix obsidian-memory SKILL.md dead file reference
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:135`
Change: Replace `agent_notes/services/memory_backend.py` with the real path `agent_notes/memory/memory_backend.py`.
Done when: The path in the skill's own "keep both files in sync" instruction resolves to a real file (D1).

### T08: Fix or remove `qa` skill reference in setup-agent-tracker
Blocked by: None
Files: `agent_notes/data/skills/setup-agent-tracker/SKILL.md:41`
Change: Remove the `qa` skill reference, or replace it with an actual existing consumer of the tracker config.
Done when: No reference to a nonexistent `qa` skill remains (D2).

### T09: Remove wiki-backend documentation from obsidian-memory
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:175-188`
Change: Remove the Obsidian-vs-Wiki storage choice section; only Obsidian and local backends exist (`memory_backend.py:45-50`).
Done when: SKILL.md documents no removed backend (D3).

### T10: Fix `{{MEMORY_PATH}}` substitution-timing claim
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:167`
Change: Correct the claim that `{{MEMORY_PATH}}` is substituted at build time — substitution only happens in the agent-prompt render loop (`agent_notes/services/rendering.py:351-352`), which does not touch skills at all. Leave line 198's narrower agent-prompt claim as-is (it is correct).
Done when: `dist/skills/obsidian-memory/SKILL.md:167` no longer carries a claim contradicted by the literal token still present in the built artifact (D5).

### T11: Fix `agent-notes memory add` CLI signature doc
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:62`
Change: Update the documented signature to match `agent_notes/cli.py:288-290`: add the 5th positional `project` argument and the `--description` flag.
Done when: The documented signature matches the real CLI surface in the file that calls itself the source of truth for memory record format (D6, `:14`).

### T12: Add `description` frontmatter field to obsidian-memory docs
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:34-41`
Change: Add the `description` frontmatter field that `migrate-memory/SKILL.md:56-64` requires and the backend enforces (`obsidian_backend.py:81-83,353-359`).
Done when: obsidian-memory and migrate-memory document the same frontmatter field set (D7).

### T13: Add `feedback` memory type to obsidian-memory docs
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:37,65-70,109-119`
Change: Add the `feedback` memory type, present in `migrate-memory/SKILL.md:40,49,59,84` and the backend (`obsidian_backend.py:242,398`), to obsidian-memory's type list.
Done when: A feedback note is documented as writable/expected in both skills that reference memory types (D8).

### T14: Fix dangling `rsi` reference in plugin build
Blocked by: None
Files: `agent_notes/data/plugin/claude.yaml`, `.claude-plugin/skills/refactoring-protocol/SKILL.md:3`
Change: Add `rsi` to the plugin allow-list (it has no mechanical exclusion reason — no `requires_memory`, no `stability` flag, all 8 dispatched agents are shipped), or remove the `rsi` cross-reference from refactoring-protocol's shipped copy.
Done when: The plugin build contains no reference to a skill absent from that same build (D9).

### T15: Add when-to-use clause to rails/docker descriptions
Blocked by: None
Files: `agent_notes/data/skills/rails/SKILL.md:4`, `agent_notes/data/skills/docker/SKILL.md:4`
Change: `triggers:` frontmatter is inert (zero references in `agent_notes/`) and `session_context.py:11-18` only injects name+description into the session catalog. Rewrite each description to include an explicit when-to-use clause, since it is the only live routing signal.
Done when: Both descriptions state when to fire without relying on `triggers:` (D10).

### T16: Reconcile chrome-test flag claim vs mandatory-gate language
Blocked by: None
Files: `agent_notes/data/skills/chrome-test/SKILL.md:3,14,63,91,214,259,261`, `agent_notes/data/agents/shared/verification.md:41`
Change: `claude --chrome` is unpinned and self-described (`:261`) as "a community pattern, not an officially documented Anthropic workflow," while verification.md treats the gate as mandatory. Either soften verification.md's mandatory language to acknowledge the dependency risk, or pin/verify the flag in the skill.
Done when: The mandatory-gate claim and the unpinned/unofficial flag claim no longer contradict each other (D11).

### T17: Correct ExitPlanMode hook claim
Blocked by: None
Files: `agent_notes/data/skills/obsidian-memory/SKILL.md:165`
Change: No hook implements a rule firing "After every Claude Code `ExitPlanMode` invocation" — `agent_notes/cli.py:294` only supports memory-bridge, precompact-memory-bridge, session-discover, guard-credentials. Correct the claim to state this is model-discretion compliance, not an enforced hook.
Done when: SKILL.md does not claim automatic enforcement where none exists (D12).

### T18: Close routing off-ramp gap between rsi/refactoring-protocol/improve-codebase-architecture
Blocked by: None
Files: `agent_notes/data/skills/improve-codebase-architecture/SKILL.md`
Change: `rsi` and `refactoring-protocol` each cross-reference both siblings; `improve-codebase-architecture` references neither. Add a cross-reference from `improve-codebase-architecture` to its siblings (this is a local frontmatter/body-level edit consistent with the existing `+group:` local-modification pattern, not an upstream re-sync).
Done when: All three arms of the routing triangle offer an off-ramp to the other two (D13).

## Group 4 — Vendored skills: provenance, license (C, A5, A6)

### T19: Add MIT NOTICE/THIRD-PARTY file for vendored skills
Blocked by: maintainer decision (spec.md Decisions #1)
Files: new file under `agent_notes/data/skills/` or repo root (path per maintainer decision)
Change: Per maintainer decision — add a NOTICE/THIRD-PARTY file reproducing the upstream `mattpocock/skills` MIT copyright notice (`Copyright (c) 2026 Matt Pocock`) and permission notice, covering all 16 vendored directories (48 files).
Done when: Maintainer has chosen a remediation route and it is implemented; MIT's "accompany all copies or substantial portions" requirement is satisfied (C1).

### T20: Fix README vendored-skill count and list
Blocked by: None
Files: `README.md:575`
Change: Update the vendored-skill count from 14 to 16; add `code-review` (upstream `skills/engineering/code-review`) and `setup-agent-tracker` (upstream `skills/engineering/setup-matt-pocock-skills`, de-branded) to the listed set.
Done when: README's vendored count and list match the actual 16 directories under `agent_notes/data/skills/` (C2).

### T21: Add machine-readable vendored-skill provenance manifest
Blocked by: None
Files: new manifest file (e.g. `agent_notes/data/skills/VENDORED.json` or similar), `README.md:575`
Change: Replace the single prose provenance line with a manifest listing each of the 16 vendored skills, its upstream path, the sync commit (`391a2701dd948f94f56a39f7533f8eea9a859c87`), and sync date (2026-07-10). No re-sync — this only makes the existing record machine-readable (C3).
Done when: Provenance is queryable per-skill, not only as one repo-wide prose sentence.

### T22: Migrate non-standard skill frontmatter under `metadata`
Blocked by: None (informed by T23's verification result)
Files: `agent_notes/data/skills/*/SKILL.md` (all skills using `group`, `requires_memory`, `stability`), skill-loading code that reads these keys
Change: Per spec.md Decisions #5 — move `group`/`requires_memory`/`stability` under the standard's `metadata` field so SKILL.md files can pass `package_skill.py` / claude.ai upload / Skills API validation, which rejects unknown top-level keys (allowed set: `allowed-tools, compatibility, description, license, metadata, name`).
Done when: All in-house non-standard keys live under `metadata`; skill-loading code reads them from the new location (A6).

### T23: Verify Codex CLI behavior on unknown SKILL.md frontmatter keys
Blocked by: None
Files: none (research task, informs T22 scope)
Change: OpenCode documents ignoring unknown frontmatter; Claude Code accepts all fields locally; Codex's behavior is UNVERIFIED — docs don't state it. Test or find documentation confirming whether Codex errors, warns, or silently ignores unknown keys like `group`/`requires_memory`/`stability`.
Done when: Codex's behavior is confirmed and recorded (closing the UNVERIFIED status in A5), informing whether T22 is urgent or precautionary.

## Group 5 — Documentation rot (E)

### T24: Remove `typical_class` from ADD_ROLE.md
Blocked by: None
Files: `docs/ADD_ROLE.md:16,27-33,54,101,310-318,330-338,336,359-360`
Change: Remove all `typical_class`-as-required-field claims, including the `ValueError: Missing field 'typical_class'` example that can no longer be raised. Document the real Role fields per `agent_notes/domain/role.py:14-21` (name/label/description/budget/color/typical_effort/order) and the real required set per `role_registry.py:51-54` (name/label/description).
Done when: ADD_ROLE.md's field list matches `role.py`/`role_registry.py` exactly (E1).

### T25: Document `budget` field
Blocked by: None
Files: `docs/ADD_ROLE.md`, `docs/ADD_MODEL.md`
Change: `budget` drives model selection and is documented in zero current guides. Add a section explaining its role and format to ADD_ROLE.md (and cross-reference from ADD_MODEL.md where relevant).
Done when: `budget` is documented in at least one current guide (E2).

### T26: Fix model-file-path claim in ADD_MODEL.md and ARCHITECTURE.md
Blocked by: None
Files: `docs/ADD_MODEL.md:3,44-48,399`, `docs/ARCHITECTURE.md:215,433,540`
Change: Remove the instruction to create `agent_notes/data/models/<id>.yaml` (directory does not exist). Document the real path: `seed.json` + `rules.yaml` via `catalog_loader.load_catalog`.
Done when: Following ADD_MODEL.md produces a file the loader actually reads (E3).

### T27: Fix class/typical_class selection-mechanism claim in ADD_MODEL.md
Blocked by: None
Files: `docs/ADD_MODEL.md:22-27,78-79,152-156,239-241,343-350`
Change: Correct the description of `class` → `role.typical_class` as the selection mechanism. Remove or correct the claim that `fable` is reachable only by explicit pin — `claude-fable-5-1` is the automatic orchestrator pick.
Done when: ADD_MODEL.md's selection-mechanism description matches the current resolver behavior (E4), consistent with `docs/superpowers/specs/2026-09-09-ranked-model-catalog-design.md` (E7).

### T28: Document provider_registry.py as fourth registry
Blocked by: None
Files: `docs/ARCHITECTURE.md:5`
Change: ARCHITECTURE.md claims three registries; add `provider_registry.py`, which gates all effort rendering, as the fourth.
Done when: ARCHITECTURE.md's registry count and list matches the codebase (E5).

## Group 6 — Latent defects (F)

### T29: Warn on deprecated-model fallback past rung 2
Blocked by: None
Files: `agent_notes/services/model_resolver.py:68-91`
Change: Emit a warning when the resolver ladder falls past rung 2 (where the deprecation guard is dropped) and selects a deprecated model, so the caller can distinguish a healthy pick from a deprecated fallback.
Done when: A resolver run that falls to rung 3/4 and selects a deprecated model logs/emits a warning (F1). No change to selection logic itself.

### T30: Map effort downgrade to nearest per-backend equivalent
Blocked by: None
Files: `agent_notes/services/rendering.py:259-261,194-196`
Change: When an agent's declared effort has no exact match on the target backend, map to the nearest equivalent in that backend's vocabulary instead of silently falling to the backend's `default_effort`. Preserve the documented "no cross-provider mapping" decision at `:194-196` if that is still desired — but at minimum emit a signal when a severe downgrade occurs (e.g. `max`→`medium` on a 6-value vocabulary).
Done when: An `effort: max` agent rendering to codex either resolves to the nearest equivalent, or the downgrade is surfaced rather than silent (F2).

### T31: Validate `typical_effort` at role load time
Blocked by: None
Files: `agent_notes/domain/role.py:20`, `agent_notes/services/role_registry.py:51-54`
Change: Validate `typical_effort` against the known effort vocabulary at role load time instead of accepting a bare untyped string.
Done when: A typo'd `typical_effort` value fails role load instead of silently rendering (F3).

### T32: Fix GPT class glob scaling
Blocked by: None
Files: `agent_notes/data/catalog/rules.yaml:11-13`
Change: `gpt-*-mini` has no `nano` counterpart, causing `gpt-5.4-nano`/`gpt-5-nano` and 8 others to class as `opus` (coding_index 77.4 down to 37.8, price $10.00 down to $0.05 inside one class). This is inert today (`model_class` only renders for `backend.use_model_class`, currently true only for claude, and GPT models carry only an openai alias). Fix the glob set to scale across mini/nano/opus tiers.
Done when: No GPT id classes into a tier spanning more than one order of magnitude in coding_index or price (F4). Note: verify the fix has no observable effect today per the inertness condition, and will take effect correctly if a `use_model_class` backend ever accepts openai models.

### T33: Fix accepted_providers claim in claude.yaml and set_role.py
Blocked by: None
Files: `agent_notes/data/cli/claude.yaml:30`, `agent_notes/commands/set_role.py:115`
Change: `accepted_providers: [anthropic, bedrock, vertex]` advertises two providers with no corresponding `providers/*.yaml` file (only `anthropic.yaml` and `openai.yaml` exist) and no way to actually select them (`catalog_loader.py:205`, `domain/model.py:31-33` always return the first/only alias). Remove `bedrock`/`vertex` from the declared list and from the "Compatible providers" message the CLI prints to users.
Done when: `set_role.py`'s printed provider list matches providers a user can actually activate (F5).
