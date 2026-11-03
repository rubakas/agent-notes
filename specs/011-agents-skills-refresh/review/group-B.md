# Group B scorecards

Read-only throughout. I ran `--help`, grep, diff and `validate`, and fetched the two CDN files into the scratchpad. `uv run agent-notes validate` reports 0 errors for all five skills (SKILL.md under 500 lines, descriptions under 1024 characters). The repo `data/` and `dist/` copies of all five skills are identical. The copies installed in `~/.claude/skills/` differ from the repo for all five, including HTML-REPORT.md. The installed rsi and refactoring-protocol descriptions are visibly longer than the source ones, so the install is stale. That is out of scope here but affects what users see.

## code-review
**Size:** SKILL.md 93 lines / 6829 bytes / ~1951 tokens; no references.
**Goal as an LLM reads it:** Goal: review the diff from a fixed point to HEAD on two separate axes. | Input: a fixed point (SHA, branch, tag, `HEAD~5`), the repo's standards docs, an originating issue or spec. | Output: a `## Standards` and a `## Spec` section plus a one-line summary per axis, with no cross-axis ranking. | Stops when: the aggregate is presented.
**Scores:**
- G1 pass — third person, "Use when reviewing a branch or PR, or the user says 'review since X'" (L3).
- G2 pass — all four statable.
- G3 minor — `argument-hint` says "fixed point" (L4) but L34 also takes a spec path "as an argument"; overlaps the `reviewer` agent, the harness `review` skill, `dual-review` and `af:review` (L3 does point to `reviewer`).
- W1 minor — "always carries" (L42), "Always a judgement call" (L45), "**Do not** merge" (L82). Mild and mostly scope rules.
- W2 pass.
- W3 pass — "sub-agent" is used consistently.
- W4 pass.
- W5 pass.
- W6 minor — two parallel sub-agents on one diff is acceptable fan-out, but the Spec agent is a verifier (L72-76).
- S1 pass — 93 lines, ~1951 tokens.
- S2 pass — no references.
- S3 pass — no references.
- S4 pass — numbered steps; L27 fail-fast check.
- S5 pass — no scripts.
- S6 minor — no worked example of a finding; the brief gives the format.
- S7 pass.
- E1 pass.
- E2 minor — L15 and L33 both cite issue-tracker.md.
- E3 minor — the 12-smell baseline (L47-60, 2403 bytes) is also consumed by rsi and refactoring-protocol, and is only needed in step 4 and by those skills.
- E4 — see findings.
- E5 pass — 240 characters.
- A1 pass — no `agent-notes` command is named.
- A2 pass — `git diff A...HEAD`, `git log A..HEAD --oneline` and `git rev-parse` verified (the `main...HEAD` diff ran; 62 commits on the branch).
- A3 fail — the Spec axis uses `analyst`, which has `Read, Grep, Glob, WebFetch` and `disallowedTools: Write, Edit, Bash` (agents.yaml:245-262). It is handed "the diff command" (L74) and cannot run it. In OpenCode, `analyst` only allows `git log*`. `reviewer` is fine in Claude (Bash allowed; agents.yaml:35-54) and in OpenCode (`git diff*` and `git log*` allowed).
- A4 minor — "two `Agent` tool calls" (L64) is the Claude Code name; OpenCode's tool is `task`.
- A5 minor — `docs/agents/issue-tracker.md` does not exist in this repo (`ls docs/agents` fails). `/setup-agent-tracker` is a real skill (`setup-agent-tracker/SKILL.md`, user-invoked) and writes that file. The smell baseline is pasted into the Standards brief (L69), which is correct.
- A6 pass — Fowler's smell names match the *Refactoring* 2nd edition ch.3.

**Findings:**
| ID | Sev | Rubric | file:line | Problem | Fix | Bytes saved |
|---|---|---|---|---|---|---|
| CR-1 | Medium | A3 | code-review/SKILL.md:72-76 | `analyst` has no Bash, so the Spec sub-agent cannot run the diff command it is given. | Replace L74 with: "- The diff itself: write `git diff <fixed-point>...HEAD` to a temp file and pass its path (`analyst` has no Bash), plus the commit list." | 0 |
| CR-2 | Medium | G2/E | code-review/SKILL.md:15 | The tracker doc is required unconditionally before step 1. This repo has no `docs/agents/issue-tracker.md`, so every review would stop to ask for `/setup-agent-tracker`, even when the spec is a passed path or the user says there is none. Only L33 needs it. | Delete L15. At L33 write: "…fetch via `docs/agents/issue-tracker.md` (if missing, ask the user to run `/setup-agent-tracker` or point to the spec)." | ~110 |
| CR-3 | Low | G3 | code-review/SKILL.md:4,34 | The argument-hint covers only the fixed point, but a spec path is also accepted. | `argument-hint: "[fixed point, e.g. main or HEAD~5] [spec path, optional]"` | 0 |
| CR-4 | Low | A4 | code-review/SKILL.md:64 | Claude-only tool name. | "Send a single message with two sub-agent calls (`Agent` in Claude Code, `task` in OpenCode)." | 0 |
| CR-5 | Low | E3/A5 | code-review/SKILL.md:47-60 | The baseline is consumed by rsi:42 and refactoring-protocol:19 by name only. Loading `code-review` pulls in the whole review workflow, and subagents never see it. | Move it to a sibling file (e.g. `SMELLS.md`) linked from step 3. | ~2400 out of SKILL.md |
| CR-6 | Low | W1 | code-review/SKILL.md:42,45,82 | Mild emphasis. | Lower-case "always", "Do not". | 0 |
| CR-7 | Low | Design | code-review/SKILL.md:25 | `A...HEAD` excludes uncommitted work. The skill is routed on "work-in-progress" in the harness listing, but the repo description does not claim it. | Note it, or add `git diff HEAD` for the working tree. | 0 |

**Accuracy log:**
- `git diff main...HEAD --stat`, `git log main..HEAD --oneline` → ran; the diff stat printed and the log showed 62 commits → OK.
- `analyst` tools → agents.yaml:245-262 (`tools: Read, Grep, Glob, WebFetch`, `disallowedTools: Write, Edit, Bash`) → WRONG for "diff command".
- `reviewer` tools → agents.yaml:35-54 (disallow Write, Edit; OpenCode `git diff*`) → OK.
- `docs/agents/issue-tracker.md` → absent in this repo; created by `setup-agent-tracker/SKILL.md:51,114` → OK conditional.
- `/setup-agent-tracker` → `setup-agent-tracker/SKILL.md:2`, `disable-model-invocation: true` → OK (the skill says "ask the user to run").
- Fowler smells → *Refactoring* 2nd edition ch.3 names → OK, from knowledge, not re-fetched.
- `validate` → "OK code-review/SKILL.md (93 lines)" → OK.

**Verdict:** Needs work — the Spec sub-agent (`analyst`) has no Bash for the diff the skill tells it to run, and the unconditional tracker-doc gate at L15 would stop every review in this repo.

## rsi
**Size:** SKILL.md 62 lines / 6370 bytes / ~1820 tokens; no references.
**Goal as an LLM reads it:** Goal: loop over the code improving it across about 9 quality dimensions without adding features. | Input: an optional path or scope (default whole project), a green test suite, and the user's answer on committing. | Output: a final report grouped by dimension, listing commits or uncommitted changes, tests added, deferrals and skipped items. | Stops when: two consecutive dry passes or 5 passes total.
**Scores:**
- G1 minor — description (L3) leads with a technical definition, and "hardening" / "wants hardening" is the vague phrasing the rubric flags. Triggers are 'rsi' and "hardening", with no "improve", "clean up" or "raise code quality". The installed copy has the better text.
- G2 pass — all four statable (L10, L20, L34, L62).
- G3 fail — a manual, expensive loop (5 agent types per pass, up to 5 passes, commits) with no `disable-model-invocation`. Its trigger overlaps refactoring-protocol ("clean up") and the `refactorer` agent.
- W1 fail — "EXISTING" (L10), "NEVER" (L14), "FIRST" (L15, L20), "Do NOT" (L20), "ONE" (L31), "FAIL" (L58). Only the test-integrity ones (L56, L58) are safety rules.
- W2 pass.
- W3 minor — "findings" vs "opportunities" (L21, L28); "pass" is clear.
- W4 pass.
- W5 pass.
- W6 fail — L32 spawns a `reviewer` after every atomic change ("don't use subagents to verify your own work", and spec 011 chose conditional review). Spawn count is 5 scanners per pass times 5 passes, plus coder or refactorer plus reviewer per change.
- S1 pass — 62 lines, ~1820 tokens.
- S2 pass.
- S3 pass.
- S4 pass — numbered loop, revert-on-regression, pass cap.
- S5 pass.
- S6 minor — the finding record has a format but no example.
- S7 pass.
- E1 minor — "what to hunt/fix/leave alone" is useful.
- E2 fail — green and characterization-first are said at L15, L20 and L53; atomic at L16 and L56; revert at L32 and L56; the commit question repeats refactoring-protocol:23,41. Gates duplicate the Prime invariant, 1056 bytes in total.
- E3 pass.
- E4 — see findings.
- E5 pass — 231 characters.
- A1 pass — no `agent-notes` command is named.
- A2 pass — `git revert` and `reset --hard` are named only as allowed or forbidden actions.
- A3 minor — `debugger`, `security-auditor`, `performance-profiler`, `system-auditor`, `reviewer`, `test-writer`, `coder` and `refactorer` all exist.
  - `debugger` is a one-failure investigator whose output format is the 6-heading diagnosis (debugger.md:14-34), so it cannot emit the JSON finding records.
  - `test-writer` has Write/Edit; "read-only pass" is prompt-only.
  - `refactorer` commits per step and reports commit refs (refactorer.md:8,29,45), contradicting "commit only if user said yes" (L33).
- A4 minor — says "Dispatch" generically, which is fine on both backends.
- A5 fail — L42 "the `code-review` skill's smell baseline" and L33 "the `git` skill's message format" are references to skills that sub-agents do not inherit, and no paste is instructed. Invariants (fail-first, no-feature) are not said to go into the coder or refactorer brief.
- A6 fail — L58: "Every regression/characterization test must be shown to FAIL on the unfixed code". A characterization test documents existing behaviour, so it passes by design. This contradicts L15 and L20.

**Findings:**
| ID | Sev | Rubric | file:line | Problem | Fix | Bytes saved |
|---|---|---|---|---|---|---|
| RS-1 | Medium | A6 | rsi/SKILL.md:58 | Characterization tests cannot "FAIL on the unfixed code" because they pin current behaviour. | "Every regression test must be shown to FAIL on the unfixed code…; a characterization test must pass on current code and fail when the pinned behaviour is mutated." | ~0 |
| RS-2 | Medium | G3 | rsi/SKILL.md:1-6 | Expensive, side-effecting loop auto-invocable on "clean up/harden" phrasing. | Add `disable-model-invocation: true`. | 0 |
| RS-3 | Medium | A3/E2 | rsi/SKILL.md:33,31 vs agents/refactorer.md:8,29,45 | `refactorer` commits atomically by its own body regardless of the user's "No". Same for `coder`. | Add to step 4: "Tell the agent not to commit; the main session commits." | 0 |
| RS-4 | Medium | A5 | rsi/SKILL.md:33,42,58 | Smell baseline, git message format and fail-first rule live in other skills or the lead; sub-agents never see them. | Step 4: "Paste into each agent brief: the finding record, the prime invariant, the fail-first rule and (for reviewer or refactorer) the smell list." | ~+150 |
| RS-5 | Medium | W6 | rsi/SKILL.md:32 | Reviewer after every change. | "`reviewer` confirms only for non-mechanical changes (logic, signatures); mechanical ones rely on green tests." | ~0 |
| RS-6 | Low | A3 | rsi/SKILL.md:22,26 | `debugger` for static scanning and `test-writer` as "read-only" are mismatched. | Use `reviewer` or `system-auditor` for bugs; `explorer` or `reviewer` for coverage gaps; keep `debugger` for step 5 escalation. | 0 |
| RS-7 | Low | E2/W1 | rsi/SKILL.md:12-16,51-58 | Gates restate the Prime invariant. | Cut Green-before/after (L53), Atomic (L56 first half), merge No-feature into L14. | ~450 |
| RS-8 | Low | W1 | rsi/SKILL.md:10,14,15,20,31 | Shouty caps outside safety rules. | Lower-case them except L56 and L58. | 0 |
| RS-9 | Low | G1 | rsi/SKILL.md:3 | Vague trigger. | "Runs a loop that improves existing code (bugs, performance, consistency, tests, DRY) without adding features. Use when the user says 'rsi', or asks to improve, clean up or harden a codebase. For one refactor use refactoring-protocol." | 0 |
| RS-10 | Low | S/W6 | rsi/SKILL.md:15,20 | Writing characterization tests is a user-unrequested add, though the safety net is defensible. | Say "ask or note" if coverage is thin, or keep as is. | 0 |

**Accuracy log:**
- Agents `debugger`, `security-auditor`, `performance-profiler`, `system-auditor`, `reviewer`, `test-writer`, `coder`, `refactorer` → agents.yaml lines 299, 55, 159, 121, 35, 93, 21, 341 → OK.
- `refactorer` commits per refactoring → agents/refactorer.md:8,29,45 → contradicts L33.
- `debugger` output → agents/debugger.md:14-34 (6 headings) → mismatch with JSON finding records.
- `/improve-codebase-architecture` → exists; `disable-model-invocation: true`, so "suggest the user run" is right → OK.
- `git` skill message format → `git/SKILL.md` `#<ticket> type(scope): short description` → OK.
- `git revert` → standard → OK.
- `validate` → "OK rsi/SKILL.md (62 lines)" → OK.

**Verdict:** Needs work — it contradicts itself on characterization tests, sub-agents commit despite a "No", and a costly loop is auto-invocable.

## refactoring-protocol
**Size:** SKILL.md 61 lines / 3523 bytes / ~1007 tokens; no references.
**Goal as an LLM reads it:** Goal: safely restructure code one extraction at a time, behaviour unchanged. | Input: user's refactor request and smell, a green suite, and the commit yes/no. | Output: the refactored code, committed per step if the user said yes, otherwise listed in the report. | Stops when: the smell is gone, tests are green, one smell is addressed ("Done means").
**Scores:**
- G1 pass — L3 has what and when plus triggers 'clean this up' and "reducing duplication".
- G2 pass.
- G3 minor — no `disable-model-invocation`; triggers overlap `rsi` ("clean this up"), the `refactorer` agent (refactor, cleanup, extract, DRY, tidy up, simplify) and the code-review baseline. It never says when to delegate to `refactorer`.
- W1 minor — "must not be mixed" (L9) is fine, "Never push" and "Never achieve green by weakening tests" (L50) are safety rules, "Do not" (L13, L51-52) is mild.
- W2 pass.
- W3 pass.
- W4 pass.
- W5 pass.
- W6 minor — L13 "write characterization tests first" is unrequested tests, defensible as a safety net. L23 asks the user once and is authorised for the commit question.
- S1 pass — 61 lines, ~1007 tokens.
- S2 pass.
- S3 pass.
- S4 pass — numbered loop with a revert path.
- S5 pass.
- S6 minor — no worked example.
- S7 pass.
- E1 minor — L9 explains what refactoring is (243 bytes).
- E2 fail — the commit question and "Never push" appear at L23 and L41 (231 bytes); "Done means" restates L49-52 (218 bytes); refactorer.md:5-10 and :31 duplicate the golden rule and the no-weakening rule.
- E3 pass.
- E4 — see findings.
- E5 pass — 215 characters.
- A1 pass.
- A2 pass — no commands.
- A3 pass — it names no agent. The gap is that it never mentions `refactorer`.
- A4 pass.
- A5 minor — L19 "Work from the smell baseline in the `code-review` skill". The `code-review` skill is a full review workflow, and a `refactorer` dispatched by the main session cannot see it.
- A6 pass.

**Findings:**
| ID | Sev | Rubric | file:line | Problem | Fix | Bytes saved |
|---|---|---|---|---|---|---|
| RP-1 | Medium | G3/E2 | refactoring-protocol/SKILL.md:1-61 vs agents/refactorer.md:5-10,31 | Near-complete overlap with the `refactorer` agent body, and triggers collide. | Add: "Do it inline for a small refactor; when delegating to `refactorer`, paste this protocol and the chosen smell into the brief." | 0 |
| RP-2 | Medium | A5 | refactoring-protocol/SKILL.md:19 | The smell list is only in code-review's step 3, so loading that skill would start a review. | Inline the 12 smell names, or point at `code-review/SMELLS.md` once CR-5 exists. | ~+300 or 0 |
| RP-3 | Low | E2 | refactoring-protocol/SKILL.md:41,55-61 | Repeats L23 and the hard rules. | Step 4: "Commit per the Process answer." Cut "Done means" to its first two bullets. | ~350 |
| RP-4 | Low | E1 | refactoring-protocol/SKILL.md:9 | Definition of refactoring. | Cut to "Refactoring changes structure only; mixing in behaviour changes is a different activity." | ~120 |
| RP-5 | Low | A6/consistency | refactoring-protocol/SKILL.md:49 vs 23 | "commit them on a branch" conflicts with a user "No" on commits. | "…save them as a patch (`git diff > file`) or stash them, fix the bug…" | 0 |
| RP-6 | Low | S4 | refactoring-protocol/SKILL.md:36 | "Undo the extraction" does not say how, for uncommitted changes. | "Undo it (`git checkout -- <files>` if uncommitted, `git revert` if committed)." | ~+50 |

**Accuracy log:**
- `/improve-codebase-architecture` → exists, user-invoked → OK.
- "smell baseline in the `code-review` skill" → code-review/SKILL.md:42-60 → OK exists, wrong place to read for subagents.
- `validate` → "OK refactoring-protocol/SKILL.md (61 lines)" → OK.
- The `refactorer` body overlaps (L5-10, L31) → agents/refactorer.md → confirmed.

**Verdict:** Minor — the content is sound but duplicates the `refactorer` agent, the smell-baseline pointer does not work for subagents, and a few lines repeat each other.

## diagnosing-bugs
**Size:** SKILL.md 149 lines / 9296 bytes / ~2656 tokens; references: `scripts/hitl-loop.template.sh` (41 lines, 1164 bytes).
**Goal as an LLM reads it:** Goal: find and fix a hard bug or perf regression through six phases, built around a red-capable feedback loop. | Input: the user's reported symptom, optionally `CONTEXT.md` and ADRs. | Output: a fix, a regression test (or a documented missing seam), debug instrumentation removed, and the confirmed hypothesis stated in the commit or PR message. | Stops when: Phase 6 checklist done and the original repro is green.
**Scores:**
- G1 pass — 250 characters; triggers 'diagnose', 'debug this', "broken, throwing, failing or slow"; ends with the `debugger` pointer. "slow" is a broad trigger.
- G2 pass.
- G3 minor — no argument-hint (none needed). Overlaps the `debugger` agent (bug, broken, error, crash, regression, flaky, root cause, investigate), the harness `debug` skill and `superpowers:systematic-debugging`.
- W1 fail — "Never" (L16), "Always" (L17), "Never" (L117), bold "This is the skill" (L29), "the exact failure this skill prevents" (L75).
- W2 fail — L31 "Be aggressive. Be creative. Refuse to give up." (rubric W2 verbatim); L46 "the bug is 90% fixed"; L29 "Spend disproportionate effort".
- W3 pass.
- W4 pass.
- W5 minor — a menu of 10 loop types, but "try in roughly this order" gives a default.
- W6 pass — no spawns; L107 "Don't block on it" is fine.
- S1 pass — 149 lines, ~2656 tokens.
- S2 pass.
- S3 pass — no reference file.
- S4 pass — phases, checklists, feedback loop.
- S5 minor — L44 and L73 say "drive them with `scripts/hitl-loop.template.sh`" without saying "copy, edit, then run" (the script header says it).
- S6 minor — the hypothesis format has one example; the others are abstract.
- S7 pass.
- E1 minor — L35-44 includes "curl/CLI/Playwright" basics.
- E2 fail — the Rules block (L13-24, 646 bytes) restates Phases 1-5 line for line. The red-capable and tight-loop requirement is stated at L15-16, L29, L66-75 and L75. L91 repeats the Phase 5 aim.
- E3 pass.
- E4 — see findings.
- E5 pass — 250 characters.
- A1 pass.
- A2 pass — `git bisect run` verified: `git bisect run` prints "'git bisect run' failed: no command provided", so the subcommand exists.
- A3 minor — only the `debugger` pointer; see the Cross-skill section for the tools issue.
- A4 pass — "Playwright / Puppeteer", "curl" are generic.
- A5 minor — `scripts/hitl-loop.template.sh` exists, is relative to the skill dir, and is not a markdown link. `CONTEXT.md` and `/improve-codebase-architecture` exist.
- A6 fail — hitl script: the header (L4) says "the agent runs the script; the user follows prompts". Tested with stdin as `/dev/null`: `read -p` suppresses the `[Enter when done]` prompt (bash shows `-p` only on a terminal), `read` hits EOF, and `set -e` exits with 1. A non-TTY agent Bash tool cannot drive this.

**Findings:**
| ID | Sev | Rubric | file:line | Problem | Fix | Bytes saved |
|---|---|---|---|---|---|---|
| DB-1 | Medium | A6 | diagnosing-bugs/SKILL.md:44,73; scripts/hitl-loop.template.sh:4,19,25 | The script cannot be run by an agent via a normal Bash tool: no TTY, so it exits 1 at the first `read`. | L44: "…drive _them_: copy `scripts/hitl-loop.template.sh`, edit the steps, and ask the user to run it in their own terminal (Claude Code: `! bash <path>`) and paste the `KEY=VALUE` output." Fix the header comment to match. | 0 |
| DB-2 | Medium | W2 | diagnosing-bugs/SKILL.md:31 | "Be aggressive. Be creative. Refuse to give up." is over-prompting filler. | Delete the sentence (keep "Spend disproportionate effort here."). | 45 |
| DB-3 | Medium | E2 | diagnosing-bugs/SKILL.md:13-24 | The Rules block restates the phases. | Replace with one line: "Phases 1-6 below are in order; skip one only with a stated reason." | ~600 |
| DB-4 | Low | E2 | diagnosing-bugs/SKILL.md:66-75 | The completion criterion repeats the "tight, red-capable" definition (1003 bytes). | Compress to the 4-item checklist plus "name one command you have already run (paste invocation + output)". | ~450 |
| DB-5 | Low | W1 | diagnosing-bugs/SKILL.md:16,17,29,75,117 | Over-emphatic. | Lower-case, drop "This is the skill" and "the exact failure this skill prevents". | ~120 |
| DB-6 | Low | W2 | diagnosing-bugs/SKILL.md:46,56 | Filler claims ("90% fixed", "debugging superpower"). | Delete both lines. | ~120 |
| DB-7 | Low | G3 | diagnosing-bugs/SKILL.md:3 | Trigger overlap with `debugger`, `debug` and `superpowers:systematic-debugging`. | Keep the `debugger` pointer; ensure the `debugger` description says "single failure". | 0 |

**Accuracy log:**
- `git bisect run` → `git bisect run` (no command) → "'git bisect run' failed: no command provided" → OK.
- `scripts/hitl-loop.template.sh` → exists, 41 lines → OK.
- hitl script, stdin `/dev/null` → printed the first `>>>` line, no `[Enter when done]` prompt, exit=1 → WRONG for unattended agent use.
- `debugger` agent → agents.yaml:299-325 (`Read, Grep, Glob, Bash, WebFetch`; disallows Write/Edit) → OK.
- `CONTEXT.md`, `/improve-codebase-architecture` → exist → OK.
- `validate` → "OK diagnosing-bugs/SKILL.md (149 lines)" → OK.

**Verdict:** Needs work — the human-in-the-loop script cannot run unattended as described, and ~1.4 KB of duplicated and filler text can go.

## improve-codebase-architecture
**Size:** SKILL.md 69 lines / 5756 bytes / ~1645 tokens; references: HTML-REPORT.md (135 lines, 7718 bytes).
**Goal as an LLM reads it:** Goal: find where shallow modules could be deepened, show candidates as an HTML report, then design the chosen one with the user. | Input: the codebase, optional `CONTEXT.md` and ADRs. | Output: a self-contained HTML report in the temp directory, then (after the user picks) updated `CONTEXT.md` and optionally an ADR. | Stops when: unstated — the grilling loop has no end condition or final deliverable.
**Scores:**
- G1 minor — L3 "Scans a codebase for deepening opportunities…. Use when the user wants module or interface redesign." The jargon "deepening opportunities" and "wants X" are rubric-flagged, and it has no trigger words a user types ("architecture", "shallow modules", "testability").
- G2 minor — the stop condition is missing (see above).
- G3 pass — `disable-model-invocation: true` (L4); it correctly cannot be self-invoked and others only "suggest the user run" it. No argument needed.
- W1 minor — "Do NOT propose interfaces yet" (L58), "Never substitute" (HTML-REPORT:124).
- W2 minor — "Be visual." (L37), "No hedging, no throat-clearing" (HTML-REPORT:135).
- W3 minor — SKILL.md says Benefits (L44) and HTML-REPORT says Wins (L62); Problem/Solution are "plain English" vs "one sentence".
- W4 pass.
- W5 pass.
- W6 minor — L68 "Want me to record this as an ADR…?" is outside the request, so it is a legitimate offer; it is a fan-out of one explorer only.
- S1 pass — 69 lines, ~1645 tokens.
- S2 pass — the one link is direct (L54).
- S3 pass — the Contents list is at lines 5-13 and its anchors match the headings.
- S4 pass — numbered, with a template-token check (L56).
- S5 minor — the Mermaid and Tailwind scaffold is reference to copy, which L54 conveys.
- S6 pass — the scaffold is concrete, with a Mermaid example.
- S7 pass.
- E1 minor — "Tone" restates the glossary.
- E2 fail — HTML-REPORT "Tone" (L118-135, 1286 bytes) and L50 duplicate codebase-design/SKILL.md "Use these terms exactly… _Avoid_". L64-68 (886 bytes) duplicates domain-modeling/SKILL.md:41,64-69.
- E3 pass.
- E4 — see findings.
- E5 pass — 242 characters.
- A1 pass.
- A2 minor — `start <path>` (L35) is not an executable on Windows; it needs `cmd /c start "" <path>`.
- A3 minor — `explorer` is Read/Grep/Glob and a low-effort scout (agents.yaml:75). "Explore" is a Claude Code built-in. It is asked to judge friction, but the brief is not self-contained (see IA-2).
- A4 minor — "dispatch" is generic.
- A5 minor — `/codebase-design`, `/grilling`, `/domain-modeling` and `CONTEXT.md` exist. HTML-REPORT:57 requires a "dependency category" tag whose definition lives only in `codebase-design/DEEPENING.md:7-25`, which this skill never links.
- A6 pass — CDN versions fetched: `@tailwindcss/browser@4.3.3/dist/index.global.js` and `mermaid@11.17.2/dist/mermaid.min.js` both returned 200, and their computed sha384 hashes equal the `integrity` values in HTML-REPORT:23-24. `securityLevel:"strict"` and `<pre class="mermaid">` are valid.

**Findings:**
| ID | Sev | Rubric | file:line | Problem | Fix | Bytes saved |
|---|---|---|---|---|---|---|
| IA-1 | Medium | E2 | improve-codebase-architecture/HTML-REPORT.md:118-135 | The Tone section duplicates the glossary and lists a "never substitute" menu already in codebase-design. | Replace with: "Use the `/codebase-design` glossary terms exactly; wins bullets state the gain in glossary terms (locality, leverage)." | ~1100 |
| IA-2 | Medium | A5 | improve-codebase-architecture/SKILL.md:23-29 | `explorer` does not inherit the codebase-design skill; the friction questions and vocabulary are not said to be pasted. | "Paste the five friction questions and the glossary terms into the explorer brief." | ~+120 |
| IA-3 | Low | E2 | improve-codebase-architecture/SKILL.md:64-68 | Duplicates domain-modeling's lazy-creation and ADR rules. | "Run `/domain-modeling` as terms and decisions crystallise; offer an ADR only if a future explorer would need the reason." | ~500 |
| IA-4 | Low | G2 | improve-codebase-architecture/SKILL.md:60-69 | No stop condition or final deliverable. | Add: "Stop when the user has a chosen interface direction and the CONTEXT.md/ADR updates are written." | ~+110 |
| IA-5 | Low | W3 | improve-codebase-architecture/SKILL.md:44 vs HTML-REPORT.md:60-62 | Benefits vs Wins and the sentence-length rule differ. | Make SKILL.md L39-46 name the same fields as HTML-REPORT:54-63, or defer to it. | 0 |
| IA-6 | Low | A5 | improve-codebase-architecture/HTML-REPORT.md:57 | The dependency category is undefined here. | "…tag for the dependency category (see `/codebase-design` DEEPENING.md: in-process, local-substitutable, ports & adapters, mock)". | ~+40 |
| IA-7 | Low | A2 | improve-codebase-architecture/SKILL.md:35 | `start <path>` is not directly runnable on Windows. | "`cmd /c start \"\" <path>` on Windows". | ~+10 |
| IA-8 | Low | G1 | improve-codebase-architecture/SKILL.md:3 | Jargon and vague trigger. | "Scans a codebase for shallow modules and proposes deeper ones in an HTML report, then designs the chosen one with the user. Use when the user wants to improve architecture, testability or module/interface design. …" | 0 |
| IA-9 | Low | A6 | improve-codebase-architecture/SKILL.md:56 | The `{{`/`}}` grep would false-positive on legitimate repo excerpts (Jinja, Rails views) and "Fix every hit" would mangle them. | "Fix hits that are leftover template tokens, not code excerpts." | ~+40 |
| IA-10 | Low | W2 | improve-codebase-architecture/SKILL.md:37, HTML-REPORT.md:135 | Filler. | Delete "Be visual." and the HTML-REPORT:135 sentence. | ~230 |

**Accuracy log:**
- HTML-REPORT scaffold URLs → `curl` both → 200 both → OK.
- SRI hashes → `openssl dgst -sha384 -binary | base64` → `2ql948lIdLcGEE0/…` and `EOXBFmc3gx5mb+vn0…` → match HTML-REPORT:23-24 → OK.
- `/codebase-design` (glossary, deletion test, one-adapter rule) → codebase-design/SKILL.md:12-48 → OK.
- Design-it-twice pattern → codebase-design/DESIGN-IT-TWICE.md:3-21 → OK.
- `/grilling`, `/domain-modeling` → exist → OK.
- `explorer` → agents.yaml:75 (`Read, Grep, Glob`) → OK for discovery.
- `Explore` → harness built-in → OK.
- Dependency categories → codebase-design/DEEPENING.md:9-25 → OK, unlinked.
- `validate` → "OK improve-codebase-architecture/SKILL.md (69 lines)" → OK.

**Verdict:** Minor — the CDN pins and hashes are verified and the structure is good, but the Tone section duplicates codebase-design (~1.1 KB), the explorer brief is not self-contained, and there is no stop condition.

## Cross-skill

- **debugger agent vs diagnosing-bugs.**
  - diagnosing-bugs describes a main-session loop (reproduce, minimise, hypothesise, instrument, fix, post-mortem).
  - agents/debugger.md:3-10 is the same first four steps as a delegated investigation. It cannot fix, because it has no Write/Edit (agents.yaml:304-306).
  - The skill never says when to delegate to the agent, and the agent cannot add `[DEBUG-xxxx]` logs, so it cannot do Phase 4 in the repo.
  - Triggers collide: agent "bug, broken, error, crash, regression, flaky, root cause, why does, investigate" (agents.yaml:300) vs skill L3 "diagnose / debug this / broken / throwing / failing / slow". Also the harness skills `debug` and `superpowers:systematic-debugging`.
  - Suggested rule: the skill is the loop in the main session; delegate to `debugger` only for isolated read-only reproduction or bisecting. Add that one sentence to the skill (L3 already points to the agent).
- **refactorer / refactoring-protocol / rsi / improve-codebase-architecture.**
  - Duplication: the golden rule, one-at-a-time, run-tests-each-step, never-mix and no-weakening-tests appear in refactorer.md:5-10,31 and refactoring-protocol:13-52. rsi:14-16,56-58 adds the same plus fail-first.
  - The commit yes/no gate (refactoring-protocol:23,41 and rsi:20,33) is not known to the `refactorer` body, which commits always (refactorer.md:8,29,45).
  - The routing sentence in each description (refactoring-protocol:3 → rsi, improve-codebase-architecture:3 → refactoring-protocol / rsi, rsi:3 → refactoring-protocol) is sound and consistent. The escalation `/improve-codebase-architecture` is correctly "suggest the user run it" (it is `disable-model-invocation`) in refactoring-protocol:15, rsi:55 and diagnosing-bugs:149.
  - Trigger collision: "clean this up / tidy up / cleanup / simplify / DRY" hits the `refactorer` agent, refactoring-protocol and rsi. The harness `simplify` skill also overlaps.
  - Fix order: make rsi `disable-model-invocation: true` (RS-2), say in refactoring-protocol when to delegate to `refactorer` (RP-1), and tell `refactorer` or `coder` in rsi step 4 not to commit (RS-3).
- **Smell baseline.** code-review/SKILL.md:42-60 is the single source, consumed by rsi:42 and refactoring-protocol:19 by name only. Moving it to `code-review/SMELLS.md`, or inlining it into the briefs, fixes A5 for all three (CR-5, RP-2, RS-4).
- **Duplication with domain-modeling and codebase-design.** improve-codebase-architecture/SKILL.md:64-68 and HTML-REPORT.md:118-135 repeat domain-modeling/SKILL.md:41,64-69 and codebase-design/SKILL.md:12-48.
- **Memory note.** This repo's memory says internal architecture must not go to claude.ai artifacts. The HTML report is a local temp file with external CDN scripts only. That is consistent, and no artifact publishing occurs.

**Counts by severity (my own, from the tables above):**
- code-review: 0 High, 2 Medium, 5 Low.
- rsi: 0 High, 5 Medium, 5 Low.
- refactoring-protocol: 0 High, 2 Medium, 4 Low.
- diagnosing-bugs: 0 High, 3 Medium, 4 Low.
- improve-codebase-architecture: 0 High, 2 Medium, 8 Low.
