# Agents and orchestrator review (reviewer agent, 2026-10-30, read-only)

Paths are relative to `agent_notes/data/`. `S/` means `agents/shared/`.

## Context

- **Where the lead lives.** On Claude Code the lead is the user's own CLAUDE.md. The `lead` agent is `claude_exclude: true` (`agents.yaml:11`). The rendered CLAUDE.md is 317 lines, about 23.5k characters or 5.9k tokens. The memory doc says to aim for under 200 lines.
- **Model and pins.** The main model is `opus[1m]` at effortLevel xhigh. The pins are reasoner `claude-opus-5-5`, worker `claude-sonnet-5-5` and scout `claude-haiku-4-5`. Reasoner and worker are at effort high, against a source default of medium.
- **Installed versus source.** The installed copy is v2.35.0, while the pipx package is 2.36.0. The installed copy:
  - is missing browser-tester;
  - has the old operator-only chrome-test wording at CLAUDE.md:71 and 260;
  - has a different chrome-test SKILL, docker layout, rules.yaml, seed.json and pricing.yaml.

  Release and reinstall fix all of this.

## A. Agent frontmatter

`templates/frontmatter/claude.py:10-37` emits name, description, model, tools, disallowedTools, memory, color and effort.

**A1 (medium, VERIFIED by the lead).** The six "read-only" agents have only `disallowedTools: Write, Edit` and no `tools:`, so they inherit everything else, including Bash, Agent, Artifact and NotebookEdit. The six are reviewer, security-auditor, system-auditor, database-specialist, performance-profiler and api-reviewer.
- Fix: give them a `tools:` allowlist, as analyst, architect, devil, explorer and debugger already have.
- `disallowedTools: Bash(git push *)` would remove all of Bash, so it is not an option.

**A2 (medium).** `memory: user` is set on 13 agents, including the six read-only ones.
- Memory auto-enables Read/Write/Edit, but on the read-only agents Write is denied, so the memory instructions they receive can't be followed. The doc's recommended default scope is project.
- The `## Discoveries` relay (coder.md:34-42 and 6 others) has no consumer on the local backend.
- Fix: drop `memory:` from the read-only agents and drop the Discoveries blocks on the local backend.

**A3 (low/medium).** Unused fields that would help:
- `omitClaudeMd` (see C1);
- `maxTurns` for explorer, analyst, test-runner and browser-tester;
- `background: true` for browser-tester;
- `skills:` preloads: devops + docker, refactorer + refactoring-protocol, debugger + diagnosing-bugs. Agents with an allowlist have no Skill tool, so preloading is their only way to get a skill.

**A4 (low, VERIFIED by the lead: 18/18 installed fail).** `claude.py:21` writes the description unquoted. "Triggers: …" then breaks strict YAML ("mapping values are not allowed here"). Claude Code tolerates it today, but it is fragile. Fix: quote it.

**A5 (OK).** Model aliases and IDs, colours and effort values are valid. No `Task` appears in frontmatter.
- `disallowedTools` is redundant next to an allowlist. Low.

**A6 (low).** `lead.claude.tools` and `lead.claude.memory` (`agents.yaml:13-15`) are dead config. The Agent(...) list there is also incomplete: it omits analyst, architect, debugger, devil, integrations, refactorer and browser-tester.

## B. Prompt style

**B1 (low/medium).** Emphatic wording:
- 4 "HARD RULE", 1 "MANDATORY", about 6 MUST, 2 NEVER and 1 STOP;
- sites: `S/phase0.md:1,3,20`, `S/hard_limits.md:10-16`, `S/execution.md:3,99`, `S/guardrails.md:18,27`, `S/skeptical_verification.md:1`.

Keep the emphasis on the keep-list: credentials, no-AI-attribution, destructive confirmations, and the test-integrity rules in coder/test-writer/refactorer.

**B2 (HIGH where it spawns agents).** Verification scaffolding:
- sites: `S/skeptical_verification.md:3-7` ("dispatch devil… or reviewer… do not self-certify"), `S/verification.md:1-4, 27-37, 45-55` (a self-check gate after every phase), `S/review.md:7-10`;
- Opus 5 doc: remove explicit verification instructions, "do not use subagents to verify or double-check your own work".

**B3 (medium).** Output suppressors in `S/hard_limits.md:24-27`: "1-3 sentences", "No commentary", "Never narrate internal deliberation". The Opus 5, Sonnet 5.5 and Fable 5.1 docs all say to describe the update cadence you want instead.

**B4 (medium).** Scope expansion:
- `S/execution.md:23` says to identify hidden subtasks (tests, migrations).
- `S/pipelines.md:4` adds test-writer and tech-writer to every feature.
- The doc says not to add tests or docs that weren't asked for. `coder.md:14` already agrees with the doc, so the lead contradicts the coder.

**B5 (low).** `S/phase0.md:18` "if there is any doubt … require a plan" has the "if in doubt" overtrigger pattern.

**B6 (low).** Other cruft:
- `S/execution.md:3` "Stop and think", and the STEP choreography at `:5-57`;
- `S/review.md:34`;
- the cost-report cadence stated 3 times.

## C. Orchestrator

### C.1 Coverage

- **analyst:** never routed by the lead. Only code-review uses it.
- **devil:** appears only as a verifier, with no "challenge a plan" trigger.
- **integrations:** has no routing trigger, and is missing from the writers list (`S/hard_limits.md:12`).
- **refactorer:** has no trigger and no refactor pipeline.
- **Bugfix pipeline** (`S/pipelines.md:9`): runs explorer→coder→reviewer and skips debugger.
- **No wrong routes.** Every name exists, and writes go only to agents that have Write.
- **Duplication:** the routing list `S/execution.md:74-85` mostly repeats the agent descriptions the harness already shows.

### C.2 Skills

- **Model-invocable:** chrome-test, code-review, codebase-design, diagnosing-bugs, docker, domain-modeling, git, grilling, ingest, migrate-memory, obsidian-memory, prototype, rails, refactoring-protocol, research, rsi.
- **User-only** (`disable-model-invocation`): grill-me, grill-with-docs, handoff, improve-codebase-architecture, setup-agent-tracker, to-spec, to-tickets, triage, wayfinder.
- **The lead invokes** only git, chrome-test and obsidian-memory, all valid.
- **codebase-design:3** points the model at the user-only improve-codebase-architecture. Low.
- **No precedence** between the debugger agent and the diagnosing-bugs skill, or between the refactorer agent and the refactoring-protocol skill. Low.

### C.3 Optimality

**C1 (HIGH).** Subagents receive the whole user CLAUDE.md, the orchestrator doctrine included: about 5.9k tokens per dispatch, plus role confusion (a coder told to wait for plan approval).
- The `omitClaudeMd` field exists and is not emitted.
- Options:
  - (a) `omitClaudeMd: true` on leaf agents, plus a short restated safety include. Whether `~/.claude/rules` is skipped too is UNVERIFIED; check with a canary.
  - (b) Render the lead as a `claude --agent lead` main-thread agent and slim CLAUDE.md down.
  - (c) Set depth and concurrency env caps, and deny Agent on leaf agents.

**C2 (HIGH).** Review is mandatory after every coder run, and a medium feature spawns about 5-9 agents. The Sonnet 5.5 doc found that not launching reviewer subagents unless asked cut cost by about a third. Fix: make review conditional (the user asked, security or DB sensitive, or a large diff).

**C3 (HIGH).** There is no spawn cap. The only numbers are a floor ("2-4 agents", `S/execution.md:16`) and fan-outs; the only cap anywhere is chrome-test's 3. Fix: the Opus 5 sample paragraph plus env caps.

**C4 (HIGH).** The lead is told both to do small lookups itself and never to read source:
- allowed: `S/execution.md:34,66,87`, `S/verification.md:30`;
- forbidden: `S/hard_limits.md:11,16`, `S/guardrails.md:3-4,9`;
- doc: "Do not delegate work you can finish yourself in a handful of tool calls".

**C5 (medium, VERIFIED by the lead from CLAUDE.md).** OpenCode tool names appear in the Claude text:
- `S/hard_limits.md:8` (`task`, `todowrite`), `S/verification.md:13`, `S/review.md:24` (`task_id`);
- on Claude Code these are Agent and SendMessage, and the todo tools are off by default on current models;
- fix: a per-backend substitution.

**C6 (medium, VERIFIED by the lead against the docs).** `S/execution.md:101` says background agents can't surface permission prompts and fail silently. The doc says the prompts surface in the main session.
- Also: `S/pipelines.md:6` and `S/verification.md:41` say "run in parallel as needed", against the skill's cap of 3.

**C7 (low/medium).** The "Opus tokens are 5× Haiku" ratio depends on config. With the current pins it is opus-5-5 against haiku-4-5, 4×. Fix: drop the literal.

**C8 (medium, owner).** The Phase 0 plan plus approval applies to every fix, add, update or investigate, "regardless of prompt brevity", and the plan format is specified twice. Fable 5.1 notes that an unneeded "Want me to…?" blocks work. Options: tiered gating, native plan mode, or keep.

**C9 (medium).** Done Gate item 3 makes local memory recording a condition of every task. Claude Code's auto memory says not to save activity summaries. Fix: scope item 3 to obsidian.

**C10 (low).**
- No rule to keep working while agents run (Fable 5.1).
- The built-in Explore skips CLAUDE.md, so it is cheaper. Worth testing.
- The Bash allowlist is thin: test commands are listed literally, and `gh api` is called read-only although `gh api -X POST` writes.
- Duplication: the chrome-test paragraph appears twice, and "never one agent per bullet" four times.

## D. Correctness

- **D-5:** `agents/integrations.md:8` has an undefined "self-check".
- **D-7:** the installed copy can't dispatch browser-tester. A reinstall fixes it.
- **Checked and fine:** the config provider commands, cost-report, the credentials path, and the git and chrome-test skills.

## Spec 002 re-check

- **D1 (delegation and cap):** STRONGER, since there is now an explicit doc sample and env caps.
  - Correction: the 10× figure applies only to the OpenCode lead.
- **D2 (cruft, verification, output suppressors):** UNCHANGED to STRONGER.
- **D3 (committed dist/):** moot. `dist/` is gitignored and untracked.
- **D4 (cache shadows seed):** looks resolved. The fresher of the two now wins, though only the docstring was read.

## Top 5

1. **Context and nesting:** stop CLAUDE.md leaking into subagents and stop nested spawns (C1, A1).
2. **Delegation doctrine:** cap, self-serve and no ratio (C3, C4, C7).
3. **Review:** make it conditional and remove verify-by-agent (C2, B2).
4. **Correctness:** tool names and the permission rule (C5, C6).
5. **Read-only agents and memory plumbing:** make read-only agents truly read-only, and fix the memory plumbing (A1, A2, C9).
