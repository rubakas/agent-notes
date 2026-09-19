# 002 — Model-era tuning

## Status
Draft — awaiting decision. Investigation complete 2026-09-19. The mechanically-verifiable defects from this investigation were ALREADY FIXED and are covered in `tasks.md` as done; what remains are judgment calls that change how the whole agent system behaves.

## Context
Research against current Anthropic and OpenAI primary docs (2026-09-19) to check whether this repo's agent definitions, effort assignments and prompt text match how current frontier models actually behave. Sources: `platform.claude.com/docs` (docs.claude.com 302-redirects there), `developers.openai.com/api/docs` (platform.openai.com 301-redirects there), `learn.chatgpt.com/docs`, and the bundled `claude-api` reference skill.

## Already fixed (record only, no action)

- **F1** — `gpt-5.6-sol` was priced $2/$10 in `seed.json`; OpenAI publishes $4/$20 (confirmed on the model page and the aggregate pricing table). Fixed in `seed.json`, `pricing.yaml`, and pinned via a new `price_overrides:` block in `agent_notes/data/catalog/rules.yaml`. Consequence: `codex`/`worker` now resolves `gpt-5.6-terra` instead of `gpt-5.6-sol`, which never fit worker's $2.00 budget.
- **F2** — Claude Haiku 4.5 does not support `output_config.effort` — absent from the supported-models list at `platform.claude.com/docs/en/build-with-claude/effort`, "Not supported" in the models-overview comparison table. Whether the API errors or silently ignores it is UNDOCUMENTED. Three agents (`explorer`, `tech-writer`, `analyst`) rendered `effort: low` onto it. Fixed via an `effort_support` capability in `rules.yaml` gating emission in the renderer.
- **F3** — A `config role-effort --cli codex worker none` pin could emit TOML Codex CLI rejects — `none` is valid for the OpenAI API but not for Codex's `model_reasoning_effort` (five values only, confirmed at `learn.chatgpt.com/docs/config-file/config-reference`). Fixed by giving CLI backends their own `efforts` vocabulary, distinct from the provider's. `max` was also added to the OpenAI provider (the API has seven values).
- **F4** — `gpt-5` and `gpt-5.2` added to the catalog's `deprecated:` list, recorded as vendor supersession guidance and NOT an announced shutdown; `gpt-5.1` deliberately excluded (it carries no supersession notice despite being older).

## Findings requiring a decision

### D1 — The orchestrator's delegation stance is tuned for the previous model generation

Anthropic's own guidance: Claude Opus 5 reaches for subagents FAR more readily than Opus 4.8 did, and "delegate more" instructions carried over from the 4.8 era are now actively harmful; the current recommendation is an explicit cap on spawn count.

This repo has 31 delegation directives across the ten files composing the lead prompt, and NO spawn-count cap anywhere — grep for `at most N agent` / `cap … spawn` / `no more than N agent` returns zero hits. The only numeric guidance is a FLOOR: `agent_notes/data/agents/shared/execution.md:16` — "Medium (multiple files, cross-cutting concern): plan needed, 2-4 agents."

Named fan-outs: `agent_notes/data/agents/shared/pipelines.md:12` prescribes a five-agent parallel audit by name; `pipelines.md:4` a six-spawn feature pipeline. `agent_notes/data/agents/shared/review.md:8-10` adds up to three more per review round, and `review.md:34` permits two rounds.

The lead is forbidden from self-serving in four places — `agent_notes/data/agents/shared/hard_limits.md:11,14,16` and `guardrails.md:3-4`. `hard_limits.md:16`: "If you feel the urge to 'just quickly check a file' — STOP. Dispatch `explorer`. Every file read by the lead is a budget leak (Opus tokens are 5× Haiku)."

Direct internal contradiction: `execution.md:34` says "**Free** (do it yourself): one Read/Grep/Glob answers it" while `hard_limits.md:11` forbids the lead from reading or grepping project source at all.

The four passages pushing the other way (`execution.md:14,43,70,87`, `guardrails.md:6`) are ANTI-FRAGMENTATION rules — "never spawn one agent per bullet point" — which constrain granularity, not total volume.

Note the non-Claude backends carry a far softer stance: `agent_notes/data/global-codex.md:32-40` and `global-opencode.md:32-40` say only "Use subagents when tasks can run in parallel or require isolated context. For simple tasks, sequential operations, or single-file edits, work directly." The aggressive regime is Claude-only — exactly the surface the vendor guidance says is now inverted.

DECISION: whether to add a spawn-count cap, soften the lead's no-self-serve prohibition, resolve the `execution.md:34` / `hard_limits.md:11` contradiction, and whether the cost rationale ("Opus tokens are 5× Haiku") still holds now that the lead resolves to `claude-fable-5-1` at $10/MTok and scout to `claude-haiku-4-5` at $1/MTok — a 10× ratio, not 5×.

### D2 — Prompt cruft: 93 instances, 39 assessed as counterproductive

A pattern audit against Anthropic's published prompt-audit guidance found 93 instances of patterns now counterproductive on current models, of which 54 were assessed KEEP under the guidance's own keep-list and 39 CRUFT.

| pattern | instances | KEEP | CRUFT |
|---|---|---|---|
| Stacked pressure tokens (CRITICAL/MUST/NEVER/IMPORTANT/HARD RULE/ABSOLUTE PROHIBITION/MANDATORY) | 22 | 15 | 7 |
| Sentence-initial prohibitions | 38 | 30 | 8 |
| STEP 1/STEP 2 choreography for judgment tasks | 19 | 5 | 14 |
| Long prohibition lists without provenance | 5 | 3 | 2 |
| Fixed interim-update cadence | 3 | 1 | 2 |
| Hard word/sentence caps | 3 | 0 | 3 |
| Update suppressors | 2 | 0 | 2 |
| Anti-formatting rules | 1 | 0 | 1 |
| **TOTAL** | **93** | **54** | **39** |

The KEEP judgments were conservative and are not up for revision: all credential rules (`agent_notes/data/rules/safety.md:12,14`, `global-claude.md:13,15,20`, `skills/ingest/SKILL.md:20,27`), the no-AI-attribution rule (`rules/no-ai-attribution.md:3,5` — kept because it prohibits a failure that CURRENTLY REPRODUCES: the harness injects a `Co-Authored-By: Claude` instruction), test-integrity rules (`agents/test-writer.md:29`, `agents/coder.md:18`), and the refactoring-protocol step script (`skills/refactoring-protocol/SKILL.md:29-47`, kept because ordering IS the safety property).

The CRUFT concentrates in two places. First, output-shape rules in `agent_notes/data/agents/shared/hard_limits.md:24-27` — a 1-3 sentence cap, an anti-prose rule, a no-commentary rule, and "Never narrate internal deliberation — report outcomes only." The guidance names update suppressors specifically as now causing UNDER-narration on current models, and `:24` plus `:27` is that two-pattern stack. Second, the Phase 0→4 spine: five numbered phases with roughly 20 numbered sub-steps governing judgment tasks (`phase0.md:1-16`, `execution.md:1`, `review.md:1`, `verification.md:1`), with `execution.md:3` — "Stop and think. Do NOT touch any tool until you complete this analysis internally" — as the scaffolding cue.

Also: `agent_notes/data/agents/shared/cost_reporting.md` states its cadence instruction three times in a seventeen-line file (`:3`, `:15`, `:17`), and `:7` bakes the literal string `vs Claude Opus 4.8` into a prompt as a column header — a model version that will rot.

DECISION: how aggressively to act. This is the user's own operating doctrine, and "counterproductive per vendor guidance" is not the same as "wrong for this user." Recommend treating the output-shape rules and the triplicated cadence as the highest-value, lowest-risk edits, and the Phase spine as a separate deliberate decision.

### D3 — `dist/` is not reproducible from `data/`

Six agent classes in the committed `agent_notes/dist/claude/agents/*.md` disagree with what the current resolver produces from `agent_notes/data/`: `explorer`/`tech-writer`/`analyst` ship as `claude-sonnet-5` at effort `high` where source resolves `claude-haiku-4-5` at `low`; `debugger` ships `claude-opus-5`/`medium` where source says `claude-sonnet-5`/`high`; twelve worker agents ship `claude-opus-5` where source says `claude-sonnet-5`; `architect` ships `claude-fable-5` where source says `claude-opus-5`. `dist/codex/` DOES match.

Nothing in `tests/plugins/` asserts `dist == rebuild(data)`. Any conclusion drawn by reading `dist/` is wrong about source and vice versa.

DECISION: add a reproducibility test and rebuild, or stop committing `dist/` altogether.

### D4 — The runtime cache shadows the bundled catalog

`~/.cache/agent-notes/catalog.json` takes precedence over the bundled `seed.json` at runtime. During F1 this meant a seed-only price correction had NO effect on the developer's machine — the stale value survived in cache. This is why F1's durable fix was a `rules.yaml` override rather than a seed edit.

Not a defect per se, but an undocumented precedence rule with a real failure mode: correcting catalog data can appear to do nothing. DECISION: document the precedence, add a cache-invalidation trigger, or surface the cache's age in `doctor`.

### D5 — smaller items, no decision needed, listed for scheduling

- `agent_notes/commands/config.py:182` validates a `role-effort` pin against the PROVIDER vocabulary only, so `--cli codex worker none` still reports success at the command line even though the render now safely refuses it. UX gap: the CLI says the pin is valid, then doesn't honour it.
- `docs/ADD_MODEL.md` does not document the new `price_overrides` or `effort_support` keys.
- `agent_notes/data/agents/shared/cost_reporting.md:7` hardcodes `vs Claude Opus 4.8` (see D2).
- `docs/CLI_CAPABILITIES.md:1038` pins `anthropic/claude-sonnet-4-20250514` in an example — a model in the catalog's `deprecated:` list.
- `docs/CLI_CAPABILITIES.md:788` documents the Claude Code `attribution` default as `🤖 Generated with Claude Code`, the exact string `rules/no-ai-attribution.md:11` instructs stripping. Nothing reconciles the two.

## Out of scope

Rewriting the Phase 0-4 orchestration spine without a separate decision (D2). Re-tuning effort per agent beyond the Haiku gate already applied. Anything in `docs/superpowers/`.

## Open questions for the maintainer

1. **D1 — spawn-count cap.** Add an explicit cap on lead-spawned agents (and reconcile the `execution.md:34` / `hard_limits.md:11` self-serve contradiction), or leave the current no-cap/no-self-serve regime as-is. Tradeoff: vendor guidance says the current stance actively over-delegates on Opus 5; leaving it as-is preserves a stance the user chose deliberately and may still want, especially since the cost ratio it was justified on (5×) is now stale (actual 10×, which argues for MORE caution, not less delegation-softening).
2. **D2 — prompt-cruft remediation scope.** Strip the 39 CRUFT-flagged instances (concentrated in `hard_limits.md:24-27` output-shape rules and the Phase 0→4 spine), strip only the highest-value/lowest-risk subset (output-shape rules + triplicated cost-reporting cadence), or leave the doctrine untouched. Tradeoff: this is the user's own operating doctrine — "counterproductive per vendor guidance" is not automatically "wrong for this user," and the Phase spine in particular is structural, not cosmetic.
3. **D3 — `dist/` reproducibility.** Add a `dist == rebuild(data)` test and rebuild the six drifted agent classes now, or stop committing `dist/` and generate it at install time only. Tradeoff: a test+rebuild keeps the current committed-artifact workflow but requires fixing six agents immediately; dropping committed `dist/` removes the drift class entirely but changes how installs are distributed.
4. **D4 — cache precedence.** Document the `~/.cache/agent-notes/catalog.json`-over-`seed.json` precedence, add a cache-invalidation trigger tied to package version, or surface cache age in `doctor`. Tradeoff: documentation is cheapest but relies on developers reading it before debugging a "fix that did nothing"; invalidation/staleness-surfacing closes the failure mode but adds runtime logic.
