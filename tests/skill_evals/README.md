# Skill trigger evals (spec 009, T15)

A prompt set that checks whether the right skill is (or is not) loaded for a
realistic user request, a schema test that keeps the set honest, and a one-prompt
live runner (a spike).

| File | Purpose |
|------|---------|
| `prompts.yaml` | 140 entries: `skill`, `category`, `prompt`, `expected_behaviour` |
| `test_evals.py` | Schema test. Runs in the normal suite, calls no model |
| `runner.py` | Spike. Runs ONE prompt through `claude -p`. Not collected by pytest |
| `test_runner_parse.py` | Unit tests for the runner's stream parser, using canned stream-json |

## Schema test

```
uv run pytest -q tests/skill_evals
```

It fails when the YAML is malformed or not a list of mappings with exactly the four
non-empty string keys, when `category` is not `should_trigger` or `near_miss`, when a
`skill` is not a directory under `agent_notes/data/skills`, when any skill directory
has fewer than 3 `should_trigger` or fewer than 1 `near_miss` entry, or when there are
fewer than 100 entries.

## Categories

- `should_trigger`: the named skill must load.
- `near_miss`: sounds close but must route elsewhere. `expected_behaviour` names where
  ("routes to rsi, not refactoring-protocol", "handled by the reviewer agent").

### User-only skills

Nine skills set `disable-model-invocation: true`: grill-me, grill-with-docs, handoff,
improve-codebase-architecture, setup-agent-tracker, to-spec, to-tickets, triage,
wayfinder. The model cannot auto-trigger them. For these:

- `should_trigger` prompts are slash invocations (`/to-tickets specs/012/spec.md`);
  `expected_behaviour` describes what the skill must do once invoked.
- `near_miss` prompts are natural requests where the model must NOT run the skill
  itself (it may suggest that the user run the slash command).

## Runner (live, billed)

```
uv run python tests/skill_evals/runner.py --skill git --index 0 [--model claude-haiku-4-5]
```

`--index` counts that skill's entries in file order (both categories). The runner
copies `agent_notes/data/skills` into `<tmp>/.claude/skills/` of a throwaway dir, runs
`claude -p ... --output-format stream-json --verbose` there, and prints the prompt,
the skills loaded (from `Skill` tool_use events), usage tokens, `total_cost_usd` and
PASS/FAIL. Exit code: 0 PASS, 1 FAIL, 2 no result event.

Flags it adds so a run is non-interactive, cheap and contained:
`--tools Skill --permission-mode dontAsk --allowedTools Skill` (the only tool is Skill,
so a triggered skill cannot run git or touch files; the eval measures routing, not
execution), `--setting-sources project,local` (no user settings or hooks),
`--strict-mcp-config` (no MCP servers), `--no-session-persistence` (no transcript),
`--max-budget-usd 0.50`.

Known limits of the spike:

- The user's global `~/.claude/CLAUDE.md` still loads (`--bare` would skip it but
  needs `ANTHROPIC_API_KEY`, not OAuth), so results include whatever routing hints
  that file contains.
- Slash-invocation detection (`<command-name>` marker) is covered by the parser unit
  test only; no live slash prompt has been run.
- The live run reported `git` twice for one prompt. The cause (repeated tool call
  versus duplicated stream event) was not confirmed; the parser de-duplicates.
- One sample, one model: pass rates need repeated runs (non-deterministic).

## Live measurement and cost estimate

One live run: `--skill git --index 0 --model claude-haiku-4-5` ("commit my changes",
should_trigger). Result: PASS, `git` loaded, `total_cost_usd` 0.0289858.

Measured usage (summed over the session's API calls):

| Field | Tokens |
|-------|--------|
| input_tokens | 30 |
| cache_creation_input_tokens (all 1h) | 12,268 |
| cache_read_input_tokens | 21,098 |
| output_tokens (incl. 216 thinking) | 462 |

Rates from `agent_notes/data/pricing.yaml`, USD per MTok. There is no dedicated
"Sonnet 5.5" row; `claude-sonnet-5-5` matches the `*sonnet-5*` row (Claude Sonnet 5).

| Model | in | out | cache read | cache write 1h | Per prompt | 140 prompts |
|-------|----|-----|-----------|----------------|-----------|-------------|
| Haiku 4.5 | 1.00 | 5.00 | 0.10 | 2.00 | $0.0290 (matches the measured cost) | $4.06 |
| Haiku 5.5 | 0.10 | 0.50 | 0.01 | 0.20 | $0.0029 | $0.41 |
| Sonnet 5.5 | 2.00 | 10.00 | 0.20 | 4.00 | $0.0580 | $8.12 |
| Opus 5.5 | 4.00 | 20.00 | 0.20 | 8.00 | $0.1117 | $15.64 |

How to read it:

- Uses the Haiku 4.5 token counts for every model. Other models tokenize and think
  differently, so treat Sonnet and Opus as order-of-magnitude estimates (about 2x
  either way on output, which is the small term).
- 12,268 of the tokens are cache writes, the dominant cost. If back-to-back runs
  share a cached prefix (not verified; each run uses a different temp cwd), writes
  become reads and the 140-prompt cost drops to about $0.79 (Haiku 4.5), $0.08
  (Haiku 5.5), $1.59 (Sonnet 5.5) and $2.24 (Opus 5.5).
- Haiku 5.5 rates are the 100K-token-prompt tier, which these runs stay under.

The full set run once costs roughly $0.4 to $15.6 depending on model. Running the full
set needs owner approval; do not run it in CI or from a script by default.
