# 002 — Model-era tuning: Tasks

Tracer-bullet tickets derived from `spec.md`. Every ticket cites the finding(s) it implements. No invented work.

## Group 1 — Already fixed (F1-F4)

### T01: Correct `gpt-5.6-sol` pricing and pin the budget-eligible replacement
Blocked by: None — DONE
Files: `agent_notes/data/catalog/seed.json`, `agent_notes/data/pricing.yaml`, `agent_notes/data/catalog/rules.yaml`
Change: Already shipped. `gpt-5.6-sol` corrected from $2/$10 to OpenAI's published $4/$20; a `price_overrides:` block added to `rules.yaml` to pin the correction.
Done when: Verified — `codex`/`worker` resolves `gpt-5.6-terra` (which fits worker's $2.00 budget) instead of `gpt-5.6-sol` (F1).

### T02: Gate `effort` rendering on Haiku 4.5's lack of support
Blocked by: None — DONE
Files: `agent_notes/data/catalog/rules.yaml`, renderer (effort emission path)
Change: Already shipped. An `effort_support` capability added to `rules.yaml`, gating whether `effort` is rendered at all for a given model.
Done when: Verified — `explorer`, `tech-writer`, `analyst` no longer render `effort: low` onto `claude-haiku-4-5`, which does not support `output_config.effort` per `platform.claude.com/docs/en/build-with-claude/effort` (F2). Note: whether the API errors or silently ignores the unsupported field remains UNDOCUMENTED upstream — recorded, not resolved.

### T03: Split CLI-backend effort vocabulary from provider effort vocabulary
Blocked by: None — DONE
Files: CLI backend config/effort-mapping code (codex backend `efforts` vocabulary), `agent_notes/data/providers/openai.yaml`
Change: Already shipped. CLI backends now carry their own `efforts` vocabulary distinct from the provider's, so a `none` pin cannot reach Codex's `model_reasoning_effort` (which only accepts five values, per `learn.chatgpt.com/docs/config-file/config-reference`). `max` also added to the OpenAI provider vocabulary (API supports seven values).
Done when: Verified — `config role-effort --cli codex worker none` no longer emits a TOML value Codex CLI rejects (F3).

### T04: Add `gpt-5` and `gpt-5.2` to the deprecated list
Blocked by: None — DONE
Files: `agent_notes/data/catalog/seed.json` (or equivalent deprecated-list source)
Change: Already shipped. `gpt-5` and `gpt-5.2` added to the catalog's `deprecated:` list as vendor supersession guidance, not an announced shutdown. `gpt-5.1` deliberately excluded — it carries no supersession notice despite being older.
Done when: Verified — both ids appear in `deprecated:`, `gpt-5.1` does not (F4).

## Group 2 — Small unblocked items (D5)

### T05: Validate `role-effort` pins against the CLI vocabulary, not just the provider's
Blocked by: None
Files: `agent_notes/commands/config.py:182`
Change: `--cli codex worker none` currently reports success at the command line because validation only checks the provider vocabulary; the render now safely refuses the value, so the CLI claims success on a pin it silently doesn't honour. Validate against the CLI backend's own `efforts` vocabulary (added in T03) at pin time.
Done when: `config role-effort --cli codex worker none` fails at the CLI with an error naming the rejected value, instead of reporting success then being silently dropped at render (D5).

### T06: Document `price_overrides` and `effort_support` in ADD_MODEL.md
Blocked by: None
Files: `docs/ADD_MODEL.md`
Change: Document the two new catalog keys introduced by the F1/F2 fixes: `price_overrides` (in `rules.yaml`) and `effort_support` (capability gating effort emission).
Done when: Both keys are documented in `docs/ADD_MODEL.md` with their purpose and where they live (D5).

### T07: Remove the hardcoded `vs Claude Opus 4.8` column header
Blocked by: None
Files: `agent_notes/data/agents/shared/cost_reporting.md:7`
Change: The literal string `vs Claude Opus 4.8` is baked into a prompt as a cost-report column header and will rot as models change. Replace with a comparison that does not name a specific model version (e.g. a relative/baseline framing), or derive the label dynamically.
Done when: `cost_reporting.md` no longer hardcodes a specific model name in a column header (D5, also referenced in D2).

### T08: Replace deprecated model pin in CLI_CAPABILITIES.md example
Blocked by: None
Files: `docs/CLI_CAPABILITIES.md:1038`
Change: The example pins `anthropic/claude-sonnet-4-20250514`, which is in the catalog's `deprecated:` list. Replace with a current, non-deprecated model id.
Done when: The example in `docs/CLI_CAPABILITIES.md:1038` pins a model not on the deprecated list (D5).

### T09: Reconcile documented Claude Code attribution default with the no-AI-attribution rule
Blocked by: None
Files: `docs/CLI_CAPABILITIES.md:788`, `agent_notes/data/rules/no-ai-attribution.md:11`
Change: `CLI_CAPABILITIES.md:788` documents the Claude Code `attribution` default as `🤖 Generated with Claude Code` — the exact string `no-ai-attribution.md:11` instructs stripping. Nothing reconciles the two; a reader following one doc contradicts the other. Add a note in `CLI_CAPABILITIES.md` that agent-notes overrides/strips this default, or otherwise reconcile the two statements.
Done when: The two docs no longer make contradictory claims about what attribution string ships (D5).

## Group 3 — Gated on maintainer decision (D1-D4)

### T10: Add lead spawn-count cap and resolve self-serve contradiction
Blocked by: maintainer decision (spec.md Open questions #1, D1)
Files: `agent_notes/data/agents/shared/execution.md:16,34`, `agent_notes/data/agents/shared/hard_limits.md:11,14,16`, `agent_notes/data/agents/shared/guardrails.md:3-4,6`, `agent_notes/data/agents/shared/pipelines.md:4,12`, `agent_notes/data/agents/shared/review.md:8-10,34`
Change: Per maintainer decision — add an explicit spawn-count cap for the lead (vendor guidance: Opus 5 over-delegates relative to Opus 4.8, and the current prompt has 31 delegation directives, five- and six-agent named fan-outs, and no cap anywhere); resolve the direct contradiction between `execution.md:34` ("Free: do it yourself: one Read/Grep/Glob answers it") and `hard_limits.md:11` (forbids the lead from reading/grepping project source at all); and re-evaluate whether the "Opus tokens are 5× Haiku" cost rationale in `hard_limits.md:16` still holds now that the lead resolves to `claude-fable-5-1` ($10/MTok) and scout to `claude-haiku-4-5` ($1/MTok) — a 10× ratio.
Done when: Maintainer has chosen an approach; the cap (if added) is present in the lead prompt files; the `execution.md:34`/`hard_limits.md:11` contradiction no longer exists; the cost rationale string matches the current resolved price ratio (D1).

### T11: Act on prompt-cruft findings per maintainer-chosen scope
Blocked by: maintainer decision (spec.md Open questions #2, D2)
Files: `agent_notes/data/agents/shared/hard_limits.md:24-27`, `agent_notes/data/agents/shared/cost_reporting.md:3,15,17`, phase-spine files (`phase0.md:1-16`, `execution.md:1,3`, `review.md:1`, `verification.md:1`) — scope per maintainer decision
Change: Per maintainer decision on remediation aggressiveness (spec.md recommends output-shape rules + triplicated cadence as highest-value/lowest-risk, with the Phase 0→4 spine as a separate deliberate call). Candidate edits: strip or soften the 1-3 sentence cap, anti-prose rule, no-commentary rule, and "never narrate internal deliberation" stack in `hard_limits.md:24-27` (flagged as update suppressors that cause under-narration on current models); de-duplicate the cadence instruction stated three times in `cost_reporting.md` (`:3,15,17`); separately decide whether to restructure the Phase 0→4 numbered-step spine.
Done when: Maintainer has chosen a scope; the chosen subset of the 39 CRUFT-flagged instances is edited or explicitly deferred with reasoning recorded (D2).

### T12: Add `dist == rebuild(data)` reproducibility test and rebuild drifted agents
Blocked by: maintainer decision (spec.md Open questions #3, D3)
Files: `agent_notes/dist/claude/agents/*.md` (six drifted classes: `explorer`, `tech-writer`, `analyst`, `debugger`, twelve worker agents, `architect`), `tests/plugins/` (new test)
Change: Per maintainer decision — either add a test asserting the committed `dist/` matches what the resolver produces from `data/` and rebuild the six drifted agent classes (`explorer`/`tech-writer`/`analyst`: ship `claude-sonnet-5`/`high`, should be `claude-haiku-4-5`/`low`; `debugger`: ships `claude-opus-5`/`medium`, should be `claude-sonnet-5`/`high`; twelve worker agents: ship `claude-opus-5`, should be `claude-sonnet-5`; `architect`: ships `claude-fable-5`, should be `claude-opus-5`), or stop committing `dist/claude/` and generate it at install time only. `dist/codex/` already matches and needs no change.
Done when: Maintainer has chosen an approach; either `dist/claude/agents/*.md` matches a fresh rebuild from `data/` with a test enforcing it, or `dist/claude/` is removed from the committed tree (D3).

### T13: Document or mitigate runtime-cache precedence over bundled catalog
Blocked by: maintainer decision (spec.md Open questions #4, D4)
Files: `~/.cache/agent-notes/catalog.json` consumer code (catalog load path), `docs/ARCHITECTURE.md` or equivalent, `doctor` command
Change: Per maintainer decision — document that `~/.cache/agent-notes/catalog.json` takes precedence over the bundled `seed.json` at runtime (confirmed by F1's fix requiring a `rules.yaml` override rather than a seed-only edit, since a seed correction alone had no effect on a machine with a stale cache); and/or add a cache-invalidation trigger; and/or surface the cache's age in `doctor`.
Done when: Maintainer has chosen an approach; the precedence is documented, and/or cache staleness is either invalidated automatically or visible via `doctor` (D4).
