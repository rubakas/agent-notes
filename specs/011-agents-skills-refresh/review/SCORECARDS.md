# Skill scorecards: summary (2026-11-03)

These are per-skill reviews against `rubric.md`, which has 30 items drawn from the official skill and prompting docs, re-fetched on 2026-11-03.

- **Scope:** every skill except rails, plus the upstream `security-audit` we plan to vendor.
- **Method:** 5 reviewer agents, run in parallel.
- **Full scorecards:** `group-A.md`, `group-B.md`, `group-C.md`, `group-D.md` and `security-audit.md`. Each has goal sentences, every rubric score, a findings table, and an accuracy log saying how each command, path or agent was checked.
- **Lead verification:** `verification.md`. I re-read every High and most Medium findings against the file, and each one has a verdict.

The counts below are after verification. The `SA-` IDs from group A are renamed `ST-`, and the `RS-` IDs from group C are renamed `RE-`.

| Skill | Verdict | High | Med | Low | Headline |
|---|---|---|---|---|---|
| migrate-memory | Needs work | 3 | 4 | 3 | Index.md spec is wrong (CLI writes `[[stem]]`); renames break links; moves and deletes vault folders with no confirm step |
| setup-agent-tracker | Needs work | 1 | 4 | 6 | `glab issue list -F json` is wrong (`-O json`); `glab issue note` *does* read stdin; `gh issue list` default limit is 30; `--comments` + jq; sub-issue command missing |
| docker | Needs work | 1 | 4 | 6 | Postgres tuning env vars the image ignores; redis healthcheck fails with `requirepass`; deprecated `npm ci --only=production` ×4; a multi-stage example that can't build; `pipefail` under dash |
| obsidian-memory | Needs work | 0 | 6 | 6 | Claims an OpenCode session id the code doesn't implement; wrong Index layout; repo-developer section shipped to users; duplicates and contradicts the injected memory text |
| rsi | Needs work | 0 | 5 | 5 | Contradicts itself on characterization tests; subagents commit despite a "no"; auto-invocable costly loop; reviewer after every change; unreachable skill references |
| code-review | Needs work | 0 | 2 | 5 | Spec axis given to `analyst` (no Bash) with a diff command; tracker doc required even when not needed |
| diagnosing-bugs | Needs work | 0 | 2 | 5 | HITL script can't run from the agent's Bash (no TTY); "Be aggressive… Refuse to give up" |
| prototype | Needs work | 0 | 3 | 5 | UI.md route rule contradicts itself; commits to a throwaway branch without the ask SKILL.md requires; about 1.3 KB of duplication |
| research | Needs work | 0 | 2 | 3 | No agent type, and the agent must Write the file (Claude Code refuses subagent report writes); injection rule never reaches the agent |
| ingest | Minor | 0 | 4 | 5 | `memory show` confirm step fails under per-project; no `--description`; about 2 KB of duplication; vault-writing skill auto-triggers on "learn from the codebase" |
| chrome-test | Minor | 0 | 3 | 5 | 99.7% of the token limit; rules repeat; "always re-test" vs "optionally" |
| wayfinder | Minor+ | 0 | 2 | 5 | "update or delete those tickets" with no confirm; depends on the incomplete GitHub seed |
| to-tickets | Minor | 0 | 1 | 5 | "Work the frontier" reads as an instruction to start implementing |
| to-spec | Minor | 0 | 1 | 3 | One sentence carries four rules |
| refactoring-protocol | Minor | 0 | 2 | 4 | Duplicates the refactorer agent; smell list unreachable for subagents |
| improve-codebase-architecture | Minor | 0 | 2 | 8 | Tone section duplicates codebase-design; explorer brief not self-contained; no stop condition |
| codebase-design | Minor | 0 | 1 | 10 | "delete old tests" with no same-behaviour condition; about 2 KB of generic text |
| domain-modeling | Minor | 0 | 0 | 7 | Layout stated in 3 files; placeholder example |
| triage | Minor | 0 | 0 | 5 | Economy (AGENT-BRIEF examples, about 1.8 KB) |
| git | OK | 0 | 0 | 4 | Over-broad "says 'git'" trigger |
| handoff | OK | 0 | 0 | 2 | — |
| grilling [frozen] | Minor | 0 | 0 | 5 | Vague description; "relentlessly"; collides with the devil agent |
| grill-me [frozen] | Minor | 0 | 0 | 2 | No "Use when" (validator warning) |
| grill-with-docs [frozen] | Minor | 0 | 0 | 2 | No "Use when"; "ADR's" typo |
| **security-audit** (upstream) | Not vendorable as Req 10 stands | 1 | 11 | 16 | No `confirmed` possible on Claude Code without a resource-limited sandbox; 13 gaps in Req 10 (critic pastes the whole ledger, explorer asked for host facts, two files can never pass our contents check, 12 links not 11, git-history secret leaks…) |

**Totals:** 6 High, 59 Medium, 132 Low, across 25 skills.

## Cross-skill themes

1. **Subagents never see skills.** rsi, refactoring-protocol, improve-codebase-architecture and research point agents at skill content they can't load. The code-review smell list belongs in its own file, `code-review/SMELLS.md`, so every brief can paste it.
2. **Side-effecting skills that can trigger themselves:** rsi, ingest and migrate-memory. Each needs `disable-model-invocation: true`.
3. **Memory docs drift from the code.** Layout, frontmatter and index rules are stated in obsidian-memory, ingest, migrate-memory and `memory/instructions.py`, and they disagree with each other and with `obsidian_backend.py`. obsidian-memory should be the only owner; the others link to it and use `memory index` / `memory init`.
4. **The trackers' shared preamble is copied 4–5 times** (the untrusted-content paragraph, "read issue-tracker.md or run /setup-agent-tracker"). It's defensible as safety text. Only the unconditional gate in code-review is a bug.
5. **Code bugs found while checking the docs.** These are not skill text:
   - `memory show` reads the flat layout only;
   - `[[wikilink]]` resolution is flat-only;
   - per-project storage may nest `<cwd>` twice;
   - `instructions.py:107` gives the session filename as `<session-id>.md`, but the code writes `YYYY-MM-DD_<session-id>.md`;
   - no OpenCode session id is detected.
6. **The installed copies are stale** (v2.35.0 against source). Release and reinstall fix that; out of scope.
