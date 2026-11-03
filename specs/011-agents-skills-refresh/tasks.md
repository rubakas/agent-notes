# 011 — Agents, Orchestrator and Skills Refresh: Tasks

This is the ticket index for `spec.md`.

- Paths are relative to `agent_notes/data/` unless they start with `agent_notes/`, `tests/` or a repo-root file.
- Line numbers are as of `f20fff2`. If a line has moved, edit by content, not by number.
- Each ticket ends green: `uv run pytest` on the touched area, plus `agent-notes validate`.

## Phase A — Agents (T01–T05)

- [x] **T01 Canary: what `omitClaudeMd` drops** (Req 1a; done by the lead)

  Run a headless `claude -p --no-session-persistence --agents '<inline json>'` with one agent that has `omitClaudeMd: true` and tools `Read`. Ask it whether its context contains either of these texts:
  - "You are the primary assistant" (from the user CLAUDE.md);
  - "# Code Quality" (from `~/.claude/rules/code-quality.md`).

  Run a control agent without the field. Record both observations verbatim in spec.md under "T01 results", then remove the `~/.claude/projects/<slug>/` leftovers.

  **Acceptance**: spec.md records which of CLAUDE.md and rules each agent saw. Req 1c's block content is decided from that.

- [x] **T02 Claude frontmatter template** (Req 1b, 6a)

  **Files**: `templates/frontmatter/claude.py`, `tests/unit/templates/test_claude_frontmatter.py`

  **Changes**:
  - Write `description` as a double-quoted YAML string, escaping `"` and `\`.
  - Emit `omitClaudeMd` and `background` when the agent's `claude:` block sets them. The field order is unchanged for existing fields.

  **Acceptance**: unit tests cover a quoted description containing `: ` and `"`, `omitClaudeMd` emitted and absent, and `background` emitted.

- [x] **T03 agents.yaml** (Req 1b, 1d, 1e, 1f, 6b; after T02)

  **Files**: `agents/agents.yaml`, `tests/unit/services/` (new test file, or extend `test_browser_tester_agent.py`)

  **Changes**:
  - Every agent with Claude output gets `claude.omitClaudeMd: true`.
  - reviewer, security-auditor, system-auditor, database-specialist, performance-profiler and api-reviewer each get:
    - `claude.tools: "Read, Grep, Glob, Bash, WebFetch"`;
    - `disallowedTools` removed;
    - `memory:` removed.
  - `browser-tester` gets `claude.background: true`.
  - Delete `lead.claude` (lines 13-15).

  **Acceptance**: tests cover:
  - every rendered Claude agent parses with `yaml.safe_load`;
  - every one has `omitClaudeMd: true`;
  - no `tools` value contains `Agent`;
  - the six analysis agents have the exact allowlist and no `memory`.

- [x] **T04 Restated rule block + Discoveries gating** (Req 1c, 1e; after T01, T03)

  **Files**:
  - `agents/shared/agent_rules.md` (new, at most 25 lines);
  - every `agents/*.md` agent body except `lead.md`, which gets `<!-- include: agent_rules -->`;
  - the `## Discoveries` blocks in `coder.md`, `test-writer.md`, `test-runner.md`, `devops.md`, `tech-writer.md`, `integrations.md` and `refactorer.md`;
  - `agent_notes/services/rendering.py` (gating);
  - tests.

  **Changes**:
  - The block content follows T01.
  - The Discoveries blocks render only when the memory backend is obsidian, via the same mechanism `{{MEMORY_INSTRUCTIONS}}` uses.

  **Acceptance**:
  - The rendered Claude coder contains the credential and attribution lines.
  - On the local backend it has no `## Discoveries`; on obsidian it does.
  - OpenCode and Codex output is unchanged apart from the include.

- [x] **T05 Subagent caps in settings.json** (Req 2c)

  **Files**:
  - `agent_notes/services/settings_writer.py` (an env entry install/remove, following `install_allow_entry`/`remove_allow_entry`);
  - the install and uninstall call sites;
  - install state;
  - tests under a fake HOME.

  **Changes**:
  - Merge `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH="1"` and `env.CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS="5"` only when each key is absent.
  - Record what was written.
  - Uninstall removes a key only if its value is still the one we wrote.

  **Acceptance**: tests cover:
  - fresh install writes both keys;
  - an existing user value is kept;
  - uninstall removes ours and keeps a user-changed one;
  - re-install is idempotent.

## Phase B — Lead text (T06–T07)

- [x] **T06 Lead shared text rewrite** (Req 2a, 2b, 2d–2g, 3, 4, 5b–5e)

  **Files**:
  - `agents/shared/execution.md`, `hard_limits.md`, `guardrails.md`, `phase0.md`, `pipelines.md`, `review.md`, `verification.md`, `skeptical_verification.md`, `cost_reporting.md`;
  - `agents/integrations.md:8`.

  **Changes**: exactly as spec Req 2–5, item by item.
  - Keep the keep-list wording emphatic.
  - Keep the chrome-test objective-trigger sentence intact.
  - Keep the Done Gate honesty rule.

  **Acceptance**:
  - `agent-notes build` succeeds.
  - The spec SC-006 and SC-007 gates pass on the rendered `~/.claude/CLAUDE.md` equivalent in the build output.
  - The OpenCode lead renders without errors.

- [x] **T07 Backend-specific tool names** (Req 5a; after T06)

  **Files**: `agent_notes/services/rendering.py`, the shared files that name dispatch, resume or todo tools, and tests.

  **Changes**:
  - Add a placeholder, for example `{{AGENT_TOOL}}`, `{{RESUME_TOOL}}` and `{{TODO_LINE}}`, substituted per backend:

    | Backend | `{{AGENT_TOOL}}` | `{{RESUME_TOOL}}` | `{{TODO_LINE}}` |
    |---|---|---|---|
    | Claude Code | `Agent` | `SendMessage` | empty |
    | OpenCode | its names | its names | its names |
    | Codex | its names | its names | its names |

  - Verify the OpenCode and Codex names against their docs, and cite the URLs in the commit's ticket note.

  **Acceptance**: the rendered Claude CLAUDE.md has no `todowrite`, `` `task` `` or `task_id`, and the OpenCode lead keeps working names. Both are covered by tests.

  **Note** (names verified 2026-11-03; substitution is `_substitute_tool_names` in `agent_notes/services/rendering.py`):
  - Claude Code: `Agent`, `SendMessage`, no todo tool. Source: https://code.claude.com/docs/en/sub-agents.md
  - OpenCode: `task` and `todowrite`. Sources: https://opencode.ai/docs/tools/ (built-in tool list) and https://opencode.ai/docs/agents/ ("subagents via the Task tool with `permission.task`"). No resume parameter is documented, so the text says: send the correction to the same subagent session if the CLI supports it, otherwise start a new one with the prior findings.
  - Codex: neutral wording only ("spawn a subagent", "steer the same subagent thread"), no todo line. The page names no tool functions: https://developers.openai.com/codex/subagents, which redirects to https://learn.chatgpt.com/docs/agent-configuration/subagents

## Phase C — Skills (T08–T09)

- [ ] **T08a Skill fixes: process and quality skills** (Req 7; after T09 for any file both tickets touch)

  **Skills**: code-review (with the new `SMELLS.md`), rsi, refactoring-protocol, diagnosing-bugs (and `scripts/hitl-loop.template.sh`), improve-codebase-architecture, to-spec, to-tickets, wayfinder, triage, setup-agent-tracker and handoff.

  **Changes**:
  - Apply the Req 7 table rows for these skills, ID by ID.
  - Each fix is the "Fix" column of `review/group-A.md` or `review/group-B.md`, as amended by `review/verification.md`.
  - Re-check each premise before editing, and stop and report if one no longer holds.

  **Acceptance**:
  - The ticket note lists every ID as done or skipped.
  - SC-014 passes for these skills.
  - `agent-notes validate` reports 0 errors.

- [ ] **T08b Skill fixes: design, tooling and the grill descriptions** (Req 7)

  **Skills**:
  - codebase-design, domain-modeling, prototype, research, git, docker;
  - chrome-test, with the new `REQUEST-TEMPLATE.md` and `MANUAL-FALLBACK.md`;
  - the grill trio (descriptions and argument-hint only);
  - the migrate-memory stopgap (MM-6 only).

  **Changes**: as T08a, from `review/group-C.md` and `review/group-D.md`.
  - docker: DK-1 to DK-5 are copy-paste correctness fixes. Check each against the cited vendor docs (hub.docker.com/_/postgres, docs.docker.com best practices) or a local `--help`, and cite the source in the note.

  **Acceptance**:
  - The ticket note lists every ID as done or skipped.
  - SC-008 and SC-014 pass.
  - chrome-test SKILL.md is at most 14,000 bytes.
  - `agent-notes validate` reports 0 errors and 0 warnings once both T08 tickets are done.

- [x] **T09 Upstream partial pulls** (Req 8)

  **Files**:
  - `skills/setup-agent-tracker/issue-tracker-github.md`, `issue-tracker-gitlab.md` and `SKILL.md`;
  - `skills/to-tickets/SKILL.md`, `skills/wayfinder/SKILL.md`, `skills/diagnosing-bugs/SKILL.md`, `skills/improve-codebase-architecture/SKILL.md`, `skills/domain-modeling/SKILL.md`;
  - `THIRD_PARTY_SKILLS.yaml`.

  **Source**:
  - The upstream clone is in the session scratchpad, `upstream/repo/` at `a496f55`.
  - Copy hunks by reading the upstream commit diffs (`git -C <clone> show <sha> -- <path>`), never from memory. See `feedback-writer-agents-invent-code`.

  **Changes**: exactly as Req 8.
  - For glab, check each flag against docs.gitlab.com/cli for the command used, and cite the URL.

  **Acceptance**:
  - SC-009 passes.
  - The grep gates for `--body "`, `cdn.tailwindcss.com` and `securityLevel: "loose"` return 0 hits in `skills/`.
  - `THIRD_PARTY_SKILLS.yaml` lists the applied SHAs per skill.

- [ ] **T13 Import `security-audit`** (Req 10a–10j)

  **Files**:
  - `skills/security-audit/`: 18 vendored files (SKILL.md, 14 reference `.md` files, `report-schema.json` and 2 validator `.cjs` files), plus the new `PLANNING.md` (and `WRITE-ISOLATION.md` only if 10c needs it);
  - `THIRD_PARTY_SKILLS.yaml`;
  - `README.md` and `CHANGELOG.md`, the 10j lines only.

  **Source**:
  - `cp` from the clone at `c1c8a8c`, in the session scratchpad at `upstream-cloudflare/repo/skills/security-audit/`.
  - Moved sections are cut and pasted by line range (`sed -n '88,135p'`), never retyped. See `feedback-writer-agents-invent-code`.

  **Changes**: exactly as Req 10b–10g, 10i and 10k–10v, in that order. 10r replaces 10h, and 10m, 10o, 10p, 10q and 10t amend 10f, 10c, 10d and 10e.

  **Acceptance**: SC-012 and SC-015, plus `agent-notes validate` with 0 errors and no new warnings.

- [ ] **T14 Canary: security-auditor as hunter** (Req 10f, SC-013; done by the lead; after T03, T04 and T13)

  - Run a headless `claude -p --no-session-persistence --agents '<rendered security-auditor json>'`. The prompt carries a minimal hunter brief:
    - the 10m override line;
    - the role preamble;
    - one toy coverage unit on a scratch fixture file;
    - the "return exactly one JSON object" contract.
  - Check that the reply parses as one JSON object.
  - Record the verbatim reply in spec.md under "T14 results", and clean up the leftovers.
  - If it fails, stop and report to the owner with the Req 10 fallback. Do not apply the fallback unasked.

## Phase D — Docs, live check, validation (T10–T12)

- [ ] **T10 Docs and evals** (Req 9)

  **Files**: `CHANGELOG.md` (Unreleased), `README.md` (agent tools and lead wording), `tests/skill_evals/prompts.yaml` (changed descriptions only).

  **Acceptance**: `uv run pytest tests/skill_evals -q` passes.

- [ ] **T11 Live dispatch check** (SC-010; done by the lead, after `agent-notes build` into a sandbox HOME or a headless run with the rendered agent file)

  - Dispatch one rendered agent, for example `explorer`.
  - Confirm it returns a summary, that its context lacks "You are the primary assistant", and that `Agent` is not in its tools.
  - Clean up the leftovers.

- [ ] **T12 Final validation** (all)

  Run:
  - `uv run pytest` on 3.14 and 3.11;
  - `agent-notes build`;
  - `agent-notes validate`;
  - the SC-005 to SC-009 gates;
  - the real-HOME snapshot diff before and after the test suite.

## Dependencies

| Ticket | Depends on |
|---|---|
| T02 | — |
| T03 | T02 |
| T04 | T01, T03 |
| T05 | — |
| T06 | — |
| T07 | T06 |
| T08 | — |
| T09 | — |
| T08a | T09, for files both touch |
| T08b | — |
| T13 | — |
| T14 | T03, T04, T13 |
| T10 | T01–T09, T13, T14 |
| T11 | T10 |
| T12 | T11 |

**Order:**
1. T01 runs first; it is a live probe.
2. T05, T06, T08b, T09 → T08a and T13 then run in parallel, alongside T02 → T03.
3. T04 runs after T01 and T03, and T07 after T06.
4. T14 runs after T04 and T13.
5. Then T10, T11 and T12.

**Planned coder batches**, presented for approval with the implementation plan:
- A: T02 + T03 + T04;
- B: T05;
- C: T06 + T07;
- D: T09 then T08a;
- G: T08b;
- F: T13;
- E: T10.
