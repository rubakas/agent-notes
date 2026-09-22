# 001 — Skills and Catalog Audit

## Status
Partially remediated (as of 2026-09-19). Investigation completed 2026-09-19; most BROKEN and Group E doc findings have since been fixed. Three items are deliberately held pending a maintainer decision — see below. Findings below are left as originally written (the audit record); this section tracks what has changed since.

**Remediated, verified against source:**
- A2 — `~/.codex/skills/` is no longer written; `agent_notes/data/cli/codex.yaml` now sets `skills: false` with a comment explaining Codex reads `.agents/skills`/`~/.agents/skills`, not `~/.codex/skills`.
- B1, B2, B3 — `agent_notes/data/pricing.yaml` rewritten with per-model anchored pins: Sonnet 5 separated from legacy Sonnet, Fable 5 and 5.1 split (5.1 carries its own `cache_read: 0.25`, no longer inherited from a shared glob), and all 13 OpenAI models priced individually instead of one flat `gpt-*` glob.
- C2 — README now correctly says "16 engineering/productivity skills" (was 14).
- C3 — corrected to 46 commits in this finding, above.
- D1, D2, D3, D4, D5, D6, D7, D8, D9 — wiki backend swept from `obsidian-memory/SKILL.md` and from `tests/plugins/test_skills.py`'s `VALID_MEMORY_BACKENDS` (now derived as `set(_REGISTRY) - _REMOVED_BACKENDS`); the `memory_backend.py` path, the `qa` skill reference, the `{{MEMORY_PATH}}` build-time-substitution claim, the `memory add` argument list, the `description`/`feedback` fields, and `rsi`'s plugin exclusion are all corrected at their respective sources.
- E1 — `typical_class` removed from `docs/ADD_ROLE.md`; the guide now documents `budget` instead.
- E2 — `budget` is now documented in `docs/ADD_ROLE.md` and `docs/ADD_MODEL.md`.
- E3 — `docs/ADD_MODEL.md` and `docs/ARCHITECTURE.md` no longer instruct creating `data/models/<id>.yaml`; both point at `seed.json` + `rules.yaml`.
- E4 — `docs/ADD_MODEL.md` now states plainly that `class` does not affect automatic selection.
- E5 — `docs/ARCHITECTURE.md:5` now names all four registries (CLIs, Models, Roles, Providers).
- F1 — landing on a deprecated model via the widened ladder now emits a stderr warning (`model_resolver.py::_warn_deprecated_selection`).
- F2 — an unsupported effort value now emits a stderr warning naming the requested and fallback values (`rendering.py:264-269`).
- F3 — `typical_effort` is now validated at role-load time (`role_registry.py` calls `validate_effort`).
- F4 — NOW FIXED. `agent_notes/data/catalog/rules.yaml:14-16` now carries `gpt-*-mini`, `gpt-*-nano`, and `gpt-6*` class rules with an explanatory comment; the "no nano tier" gap this finding described is closed.
- F5 — user-visible symptom FIXED; underlying data declaration remains inert (downgraded from a live bug to a data-hygiene note). `agent_notes/commands/set_role.py` now prints `configured_providers(backend)`, which filters to providers that actually exist, so users no longer see bedrock/vertex advertised. `agent_notes/data/cli/claude.yaml:30` still declares `accepted_providers: [anthropic, bedrock, vertex]`, but nothing surfaces it to a user anymore.
- D10 — WITHDRAWN 2026-09-20. The finding's premise ("`triggers`, `argument-hint`, `disable-model-invocation` are parsed by nothing") is false: grepping `agent_notes/**/*.py` returns 10, 4, and 18 references respectively.
- D11 — ADDRESSED. `agent_notes/data/skills/chrome-test/SKILL.md:16` now carries an explicit `## Precondition — claude --chrome is unverified` section.
- D12 — WITHDRAWN 2026-09-20. The finding claims `obsidian-memory/SKILL.md` asserts an `ExitPlanMode` hook exists; the current text at `obsidian-memory/SKILL.md:182` describes Claude Code's own plan-mode file behavior and makes no claim that agent-notes implements a hook.

**Not re-verified in this pass (status unknown, not required by this spec's acceptance criteria):** A5, A7, C4, C5, C6, D13.

**Path correction:** the CLI-role-effort validation logic discussed under spec 002's D5 (item 1) lives at `agent_notes/commands/config.py:182` and `:190-193`. An earlier draft of that material cited `agent_notes/services/config.py`, which does not exist.

**Deliberately held pending maintainer decision — do not mark as done:**
- C1 (MIT attribution) — `THIRD_PARTY_SKILLS.yaml` now exists as a provenance manifest but its own text explicitly defers the NOTICE/THIRD-PARTY question to the maintainer.
- A6 (non-standard frontmatter keys) — `group`, `requires_memory`, `stability` are still top-level keys in `obsidian-memory/SKILL.md` and other in-house skills, not migrated under `metadata`.
- B4 (price source of truth) — `tests/unit/cost/test_pricing_seed_divergence.py` now fails on any `seed.json`/`pricing.yaml` divergence, satisfying this spec's stated acceptance criterion, but the maintainer has not ratified which of the three original options (derive `pricing.yaml` from `seed.json`, keep both plus a guard test, or something else) is the intended long-term mechanism — the guard test is a stopgap, not a confirmed architecture decision.

E6 remains explicitly out of scope (dated historical docs under `docs/superpowers/`).

## Context
A read-only audit ran across four workstreams: skill delivery targets (web research against primary docs), vendored-skill drift vs upstream, in-house skill content, and model catalog/provider config. This spec records what was found and what should change. It is the investigate output of an investigate → spec → tickets → build cycle.

The audit began from an assumption that agent-notes formats skills per-CLI. It does not, and does not need to — see Finding 1.

## Findings

### Group A — Skill install targets (correctness, no code transform needed)

A1. Agent Skills is an open standard (agentskills.io), originally Anthropic's, adopted by Codex CLI and OpenCode. A SKILL.md with `name` + `description` is portable across all three consumers unchanged. agent-notes copies `agent_notes/data/skills/*` verbatim to `dist/skills/*` (`agent_notes/commands/build.py:41-56`) and installs that same directory to every backend (`agent_notes/services/install_plan.py:90-92`, `install_executor.py:67-76,107-120`). VERDICT: the verbatim strategy is correct. No per-provider skill compiler is warranted.

A2. BROKEN — `~/.codex/skills/` is a dead directory. Codex CLI's documented skill paths are `$CWD/.agents/skills`, `$CWD/../.agents/skills`, `$REPO_ROOT/.agents/skills`, `$HOME/.agents/skills`, `/etc/codex/skills`, and bundled system skills (source: learn.chatgpt.com/docs/build-skills, the canonical target of developers.openai.com/codex/skills). `~/.codex/skills` appears in no OpenAI doc. agent-notes writes a full skill tree there that nothing reads.

A3. `~/.agents/skills/` — treated in the code as an incidental "universal mirror" (`install_executor.py:107-120`) — is in fact the most-consumed install target. It is read by OpenCode ("Global agent-compatible") AND by Codex CLI (USER scope). Codex is therefore already being served correctly, by the mirror rather than by the directory named for it.

A4. `~/.claude/skills/` and `~/.config/opencode/skills/` both WORK as-is.

A5. Unknown frontmatter keys: OpenCode documents "Unknown frontmatter fields are ignored." Claude Code accepts all fields when loading locally. Codex's behavior on unknown keys is UNVERIFIED — the docs do not state it. agent-notes' non-standard keys are `group`, `requires_memory`, `stability`.

A6. RISK — those non-standard keys are a hard failure for a path agent-notes may later want: `package_skill.py` / claude.ai upload / the Skills API reject unknown frontmatter with `Unexpected key(s) in SKILL.md frontmatter`. Allowed set is `allowed-tools, compatibility, description, license, metadata, name`. The standard's `metadata` field is the intended home for custom data.

A7. A genuine per-provider artifact exists upstream and is not vendored: each upstream skill now ships `agents/openai.yaml` (Codex display metadata; `policy.allow_implicit_invocation: false` on user-invoked skills). This is a sidecar, not a transform. If ever vendored, that policy key is a security-relevant control surface.

### Group B — Pricing (the only findings that cost money)

B1. BROKEN — `claude-sonnet-5` is priced twice, differently, in the same repo. `agent_notes/data/catalog/seed.json` says `price_in: 2.0, price_out: 10.0`. `agent_notes/data/pricing.yaml:21-24` says `{in: 3.00, out: 15.00}` — Sonnet 4.6's rate. Verified against the provider reference: current published Sonnet 5 pricing is $2.00 / $10.00, so seed.json is correct and pricing.yaml is wrong. Its `updated_at: "2026-07"` claims a post-Sonnet-5 review, making this a stale-copy bug. Correct values on the file's own cache ratios (0.1x / 1.25x / 2x): `{in: 2.00, out: 10.00, cache_read: 0.20, cache_write_5m: 2.50, cache_write_1h: 4.00}`. Compounding: `worker` role budget is exactly 2.0 (`agent_notes/data/roles/worker.yaml:5`), so Sonnet 5 clears the budget gate BECAUSE the catalog says 2.0, then bills as if it were 3.0.

B2. BROKEN — `agent_notes/data/pricing.yaml:57-59` prices all 13 OpenAI catalog models with one glob set (`gpt-*`, `o1*`, `o3*`, `o4*`) at a flat 2.50/10.00, under an entry still labelled "GPT-4 / o-series". Twelve of thirteen are mispriced, from 50x over (`gpt-5-nano`, true 0.05/0.40) to 5x under (`gpt-6-astra`, true 10.0/50.0). The models the resolver actually selects on the codex backend are affected: `gpt-5.6-sol` (+25% input) for three roles, `gpt-5.6-luna` (12.5x over) for scout.

B3. OPEN / PLAUSIBLE — not yet confirmed, must be checked against the live pricing page before acting. `agent_notes/data/pricing.yaml:17-20` uses one `*fable*` glob for both Fable 5 and Fable 5.1, setting `cache_read: 1.00` from the standard 0.1x-of-input rule. The provider reference states Claude Fable 5.1 has a special cache-read rate of $0.25/MTok. If correct, one glob cannot price both models and cache reads are billed at 4x for `claude-fable-5-1` — which is the automatic `orchestrator` pick and the most cache-heavy role in the system.

[RESOLVED 2026-09-20 — see Status. `pricing.yaml:22-23` now splits Fable 5.1 into its own anchored-glob entry with `cache_read: 0.25`, separate from Fable 5's `cache_read: 1.00` at `pricing.yaml:26-27`.]

B4. ROOT CAUSE, and the reason B1-B3 will recur. The catalog carries two independent price sources with nothing reconciling them: `seed.json.price_in` gates role-budget model selection, `pricing.yaml` gates cost reporting. `seed.json` is machine-refreshed (`fetched_at: 2026-09-09`); `pricing.yaml` is hand-maintained. Every catalog refresh re-opens this gap. Any fix that only corrects the numbers leaves the mechanism intact.

### Group C — Vendored skills: provenance, license, drift

C1. DECISION REQUIRED (legal, not an engineering call). Upstream `mattpocock/skills` is MIT, `Copyright (c) 2026 Matt Pocock`, unchanged since the recorded sync. MIT requires the copyright notice and permission notice to accompany all copies or substantial portions. agent-notes redistributes 16 complete skill directories (48 files) inside a packaged Python artifact. There is no `LICENSE`, `NOTICE`, or `THIRD-PARTY` file anywhere under `agent_notes/data/skills/` (verified: find returns nothing), and no per-file copyright header. The repo's only LICENSE is `MIT, Copyright (c) 2025 rubakas`, which does not mention the upstream author. `README.md:575` names the author and links the repo but does not reproduce either required notice.

C2. The README undercounts its own vendoring. It claims 14 vendored skills; there are 16. `code-review` (upstream `skills/engineering/code-review`) and `setup-agent-tracker` (upstream `skills/engineering/setup-matt-pocock-skills`, de-branded) are also upstream-derived, byte-identical to the sync commit apart from the same local edits.

C3. Provenance record is accurate but fragile. `README.md:575` records commit `391a270` (2026-07-10); verified: `391a2701dd948f94f56a39f7533f8eea9a859c87` exists upstream, is an ancestor of HEAD, author date 2026-07-10. Upstream HEAD is `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` (2026-09-18). 182 commits since the sync, 46 touching vendored directories (`git rev-list --count 391a270..HEAD -- <path>` per corrected `upstream_path`, summed over the 16 vendored paths against the upstream clone). The record is a single prose line — no manifest, no lockfile, no per-skill commit, no sync script.

Note: an earlier pass of this finding reported 45; that figure predated three `upstream_path` corrections and counted the wrong path set. 46 is the reproducible figure and is what `THIRD_PARTY_SKILLS.yaml` now records.

C4. Drift severity (~10 weeks). Structural rewrites: `grilling` (one-question-at-a-time → rounds over a frontier, new output format), `prototype/LOGIC.md` (terminal TUI → single shareable self-contained HTML file), `wayfinder` (investigation tickets → decision tickets, new parallel-research-subagent step). Substantive behavior changes: `diagnosing-bugs` (new Redact section; post-mortem handoff deleted), `improve-codebase-architecture` (new git-log hot-spot scoping step), `to-tickets` (final `/implement` handoff line deleted), `domain-modeling` (trigger rewritten). Cosmetic: `codebase-design`, `handoff`, `research`. The bulk of every diffstat is a repo-wide em-dash normalization. Local modifications are minimal and consistent: `+group:` frontmatter on all 16, plus `/setup-matt-pocock-skills` → `/setup-agent-tracker` renames.

C5. Prompt-injection re-review surface for any future sync — five items crossing capability boundaries the original review signed off on. Nothing hostile; no exfiltration, no fetch-and-execute. (a) `wayfinder/SKILL.md:115` new step firing research subagents that create throwaway `research/<name>` git branches, with `:104` weakening the one-ticket-per-session invariant. (b) `improve-codebase-architecture/SKILL.md:20-22` new unprompted `git log --oneline` history mining. (c) `diagnosing-bugs/SKILL.md:12-16` new Redact section instructing on secret handling — collides with agent-notes' absolute credentials prohibition — plus `scripts/hitl-loop.template.sh:15-16`, the only executable file in the vendored set. (d) `grilling/SKILL.md:26` new autonomous subagent dispatch inside an interactive skill. (e) `prototype/LOGIC.md:3-5` artifact now explicitly intended for external distribution.

C6. Two skills were once vendored and are now absent, per `CHANGELOG.md:13` and `CHANGELOG.md:20`: `tdd` and `writing-for-agents` (predecessor `writing-great-skills`). Upstream also has `implement`, which is the consumer that `to-tickets`' deleted final line pointed at — the `to-spec` → `to-tickets` → `implement` chain is truncated in agent-notes. Also potentially relevant and unvendored: `resolving-merge-conflicts`, `git-guardrails-claude-code`, `wizard`, `pr`, `retro`.

### Group D — In-house skill content

D1. BROKEN — `agent_notes/data/skills/obsidian-memory/SKILL.md:135` points at `agent_notes/services/memory_backend.py`, which does not exist; the module is `agent_notes/memory/memory_backend.py`. This is the skill's own "keep both files in sync" instruction, so the enforcement half is dead.

D2. BROKEN — `agent_notes/data/skills/setup-agent-tracker/SKILL.md:41` names a `qa` skill as a consumer of the tracker config. No such skill exists.

D3. STALE — `obsidian-memory/SKILL.md:175-188` documents choosing between Obsidian and Wiki storage. The wiki backend is REMOVED: `agent_notes/memory/memory_backend.py:45-50` registers only local and obsidian, with `_REMOVED_BACKENDS = {"wiki"}` raising on use.

D4. BROKEN GATE — `tests/plugins/test_skills.py:80` still lists `wiki` in `VALID_MEMORY_BACKENDS`. A skill declaring `requires_memory: wiki` passes validation and is then permanently invisible. This is a check that cannot fail on the thing it exists to catch.

D5. STALE — `obsidian-memory/SKILL.md:167` claims `{{MEMORY_PATH}}` is substituted at build time. Substitution happens only inside the agent-prompt loop (`agent_notes/services/rendering.py:351-352`); `rendering.py` contains no skill handling at all. Confirmed in the built artifact: `dist/skills/obsidian-memory/SKILL.md:167` still carries the literal token. Line 198's narrower claim (agent prompts) is correct.

D6. STALE — `obsidian-memory/SKILL.md:62` documents `agent-notes memory add "<title>" "<body>" [type] [agent]`. The real surface (`agent_notes/cli.py:288-290`) adds a 5th positional `project` and a `--description` flag. This is in the file that calls itself the single source of truth for memory record format (`:14`).

D7. CONTRADICTION — `obsidian-memory/SKILL.md:34-41` omits the `description` frontmatter field that `migrate-memory/SKILL.md:56-64` requires and retroactively injects. The backend sides with migrate-memory (`agent_notes/memory/obsidian_backend.py:81-83,353-359`).

D8. CONTRADICTION — `obsidian-memory/SKILL.md:37,65-70,109-119` omits the `feedback` memory type that `migrate-memory/SKILL.md:40,49,59,84` includes. The backend sides with migrate-memory (`obsidian_backend.py:242,398`). A feedback note is writable and expected by the migrator but invisible to the skill that declares which types exist.

D9. BROKEN IN PLUGIN BUILD — `rsi` is excluded from `agent_notes/data/plugin/claude.yaml`'s 18-name allow-list, but the shipped `.claude-plugin/skills/refactoring-protocol/SKILL.md:3` tells plugin users "For an iterative multi-dimensional cleanup loop use `rsi`" — a skill absent from that install. Of the 7 excluded skills, 6 have clear mechanical justification (`ingest`/`migrate-memory`/`obsidian-memory` are `requires_memory: obsidian` and shell out to a binary the plugin doesn't ship; `rails`/`docker` are the only `group: domain` skills; `git` encodes a house-specific commit convention). `rsi` alone has no mechanical reason — no `requires_memory`, no `stability` flag, `group: process`, and all eight agents it dispatches ARE shipped. Likely accidental.

D10. INERT FRONTMATTER — `triggers:`, `argument-hint:`, and `disable-model-invocation:` are parsed by nothing in agent-notes (`grep -rn 'triggers' --include='*.py' agent_notes/` → zero hits). They pass through verbatim into the built artifact. Only `name`, `description`, `group`, `requires_memory`, `stability` are live. This matters because `rails/SKILL.md:4` and `docker/SKILL.md:4` have descriptions with NO when-to-use clause and lean on 23- and 7-entry `triggers:` lists for routing — and `agent_notes/services/session_context.py:11-18` injects only name + description into the session catalog. Their sole routing signal never states when to fire. (Note `disable-model-invocation` IS a real Claude Code field and reaches the harness intact; it is only agent-notes that ignores it.)

[WITHDRAWN 2026-09-20 — see Status. The finding's premise is false: `triggers`, `argument-hint`, and `disable-model-invocation` are referenced 10, 4, and 18 times respectively across `agent_notes/**/*.py`.]

D11. RISKY — `chrome-test/SKILL.md` is built end-to-end on launching `claude --chrome` (`:3,14,63,91,214,259`). Nothing in the repo pins or verifies that flag. The skill concedes at `:261` that this is "a community pattern, not an officially documented Anthropic workflow", while `agent_notes/data/agents/shared/verification.md:41` treats the gate as mandatory.

[ADDRESSED 2026-09-20 — see Status. `chrome-test/SKILL.md:16` now carries an explicit `## Precondition — claude --chrome is unverified` section.]

D12. RISKY — `obsidian-memory/SKILL.md:165` states a rule firing "After every Claude Code `ExitPlanMode` invocation". No hook implements this; `agent_notes/cli.py:294` restricts hook subactions to memory-bridge, precompact-memory-bridge, session-discover, guard-credentials. Compliance is model discretion only.

[WITHDRAWN 2026-09-20 — see Status. The current text at `obsidian-memory/SKILL.md:182` describes Claude Code's own plan-mode file behavior and makes no claim that agent-notes implements a hook.]

D13. COSMETIC — routing collision. `rsi` and `refactoring-protocol` each point outward to both siblings; `improve-codebase-architecture` (vendored) references neither. Two of three arms disambiguate; the third offers no off-ramp.

### Group E — Documentation rot

E1. `docs/ADD_ROLE.md` documents `typical_class` as a REQUIRED Role field across nine lines (`:16,27-33,54,101,310-318,330-338,336,359-360`), including a `ValueError: Missing field 'typical_class'` that can no longer be raised. The field does not exist: `agent_notes/domain/role.py:14-21` is name/label/description/budget/color/typical_effort/order; `role_registry.py:51-54` requires only name/label/description.

E2. `budget` — the field that actually drives model selection — is documented in ZERO current guides (grep across ADD_ROLE.md, ADD_MODEL.md, ARCHITECTURE.md returns nothing).

E3. `docs/ADD_MODEL.md:3,44-48,399` instructs creating `agent_notes/data/models/<id>.yaml`. That directory does not exist; the live path is `seed.json` + `rules.yaml` via `catalog_loader.load_catalog`. Anyone following this guide today produces a file the loader ignores. `docs/ARCHITECTURE.md:215,433,540` repeats the same claim.

E4. `docs/ADD_MODEL.md:22-27,78-79,152-156,239-241,343-350` describes `class` → `role.typical_class` as the selection mechanism, including the claim that `fable` is reachable only by explicit pin. In fact `claude-fable-5-1` is the automatic orchestrator pick.

E5. `docs/ARCHITECTURE.md:5` claims three registries. There is a fourth, `provider_registry.py`, which gates all effort rendering and is undocumented.

E6. `never_default` survives only in `docs/superpowers/specs/2026-07-31-component-lifecycle-flag-design.md:16,21,115` and `docs/superpowers/plans/2026-08-03-...:111,113,115`. Those are dated historical records; excluded from remediation scope, noted for completeness.

E7. The only current doc that accurately describes model resolution is `docs/superpowers/specs/2026-09-09-ranked-model-catalog-design.md`.

### Group F — Latent defects (correct today, wrong under a reachable config)

F1. `agent_notes/services/model_resolver.py:68-91` — deprecation is a soft preference, not a filter. The ladder's rungs 3-4 explicitly drop the guard. No warning is emitted at `:87-90` when it falls past rung 2, so the caller cannot distinguish a healthy pick from a deprecated fallback. Verified: no deprecated model is selected today across all four backends x four roles. Tighten `worker`'s budget below 2.0, or add one more unrated frontier model, and an agent silently receives `claude-sonnet-4-5` (deprecated, coding_index 52.1).

F2. `agent_notes/services/rendering.py:259-261` — effort validation is per-resolved-model, not per-backend. An agent declaring `effort: max` rendering to codex gets silently downgraded to `medium` (openai's `default_effort`), not to `xhigh`, the nearest equivalent. `medium` is a mid value in openai's six-value vocabulary, so the downgrade is severe. The docstring at `:194-196` states "NO cross-provider mapping" as a deliberate decision; the gap is the absence of any signal.

F3. Nothing validates effort values at load time. `domain/role.py:20` types `typical_effort` as a bare `str` defaulting to `""`; `role_registry.py:51-54` does not check it. A typo renders silently.

F4. `agent_notes/data/catalog/rules.yaml:11-13` — GPT class globs do not scale. `gpt-*-mini` has no `nano` counterpart, so `gpt-5.4-nano` and `gpt-5-nano` class as opus; `gpt-5-4` is an exact-id pin. 10 of 13 GPT ids class as `opus`, spanning coding_index 77.4 down to 37.8 and input price $10.00 down to $0.05 — a 200x price range inside one class. Inert today (`model_class` renders only when `backend.use_model_class`, true only for claude, and GPT models carry only an openai alias), live the moment any `use_model_class` backend accepts openai.

[RESOLVED 2026-09-20 — see Status. `rules.yaml:14-16` now carries `gpt-*-mini`/`gpt-*-nano`/`gpt-6*` class rules closing the gap.]

F5. COSMETIC — `agent_notes/data/cli/claude.yaml:30` declares `accepted_providers: [anthropic, bedrock, vertex]`. Only `providers/anthropic.yaml` and `openai.yaml` exist. Traced: this degrades gracefully and is unreachable rather than broken — `catalog_loader.py:205` gives every model exactly one provider alias keyed by its seed block, so `domain/model.py:31-33` returns `anthropic` on the first iteration always. A user cannot activate bedrock/vertex even deliberately. `agent_notes/commands/set_role.py:115` nonetheless prints "Compatible providers: anthropic, bedrock, vertex" to the user, advertising two unusable providers.

[Downgraded 2026-09-20 — see Status. The user-visible symptom is fixed (`set_role.py` now prints filtered `configured_providers`); the underlying `accepted_providers` over-declaration in `claude.yaml:30` remains as a data-hygiene nit, not a live bug.]

## Decisions required from the maintainer

1. MIT attribution for 16 vendored skill directories (C1) — add NOTICE/THIRD-PARTY reproducing the upstream copyright and permission notice, or take another route. Legal judgment, not engineering.
2. Price source of truth (B4) — make `pricing.yaml` derive from `seed.json`, keep both and add a reconciliation test, or something else. Correcting the numbers alone leaves the mechanism that produced them.
3. `~/.codex/skills/` (A2) — stop writing it, or keep it as forward-compatible speculation. Note that removing it changes uninstall behavior for existing installs.
4. Upstream re-sync (C4, C5) — out of scope for this spec by prior decision (manifest only, no re-sync). Confirm that still holds given the three structural rewrites.
5. Non-standard frontmatter keys (A6) — migrate `group`/`requires_memory`/`stability` under the standard's `metadata` field, or accept that skills cannot be packaged/uploaded as-is.
6. ~~Fable 5.1 cache-read rate (B3)~~ — RESOLVED 2026-09-20, no longer a live decision. `pricing.yaml:22-23` now prices Fable 5.1 separately from Fable 5, with its own `cache_read: 0.25`; see Status and the B3 finding below.

## Acceptance criteria

- [ ] Every BROKEN finding (A2, B1, B2, D1, D2, D4, D9) has a fix or an explicit accepted-risk note.
- [ ] No install target is written that no consumer reads (A2 resolved one way or the other).
- [ ] A single reconciled price source, or a test that fails when `seed.json` and `pricing.yaml` diverge (B4).
- [ ] Vendored skill provenance is machine-readable, not a single prose line (C3).
- [ ] Wiki-backend references are swept from all three places: `obsidian-memory/SKILL.md` docs (D3), the test's `VALID_MEMORY_BACKENDS` (D4), and the `requires_memory` documented value set.
- [ ] Every doc statement contradicted by source (E1, E3, E4, E5) is corrected or deleted.

## Out of scope

Re-syncing vendored skill content to upstream HEAD. Building a per-provider skill compiler (A1 establishes it is unwarranted). agent-flows changes. Model catalog data refresh. Historical plan docs under `docs/superpowers/` (E6).
