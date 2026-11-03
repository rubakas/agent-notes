# Lead verification of the Medium and High findings (2026-11-03)

I read every cited line myself (sed against `agent_notes/data/skills/` at f20fff2).

- **CONFIRMED** = the cited text says what the finding claims.
- **ADJUSTED** = the claim holds, but the severity, line or fix is corrected.

The research skill's IDs are renamed from `RS-` to `RE-` to avoid clashing with rsi.

## Group B

| ID | Verdict | Evidence / note |
|---|---|---|
| CR-1 | CONFIRMED | code-review:74 says "The diff command and commit list." analyst has no Bash (agents.yaml analyst: `disallowedTools: Write, Edit, Bash`). |
| CR-2 | CONFIRMED | code-review:15 reads `docs/agents/issue-tracker.md` unconditionally before any step. |
| RS-1 | CONFIRMED | rsi:58 says "Every regression/characterization test must be shown to FAIL on the unfixed code". A characterization test pins current behaviour, so it passes on unfixed code. |
| RS-2 | CONFIRMED | The rsi frontmatter (lines 1–6) has no `disable-model-invocation`, and the description says "wants hardening". |
| RS-3 | ADJUSTED | refactorer.md:8 says "small commits" and :29 says "Keep commits atomic", so the agent does commit. The :45 cite is wrong (it is the smells list); the claim stands without it. |
| RS-4 | CONFIRMED | rsi:33 says "Use the `git` skill's message format"; rsi:42 says "the `code-review` skill's smell baseline". No instruction says to paste either into a brief. |
| RS-5 | CONFIRMED | rsi:32 says "`reviewer` confirms" after every change. |
| RP-1 | CONFIRMED | The refactorer.md:8 one-at-a-time and commit rule overlaps refactoring-protocol. The skill never mentions the agent. |
| RP-2 | CONFIRMED | refactoring-protocol:19 says "Work from the smell baseline in the `code-review` skill". |
| DB-1 | CONFIRMED | hitl-loop.template.sh:4 says "The agent runs the script". Lines 19 and 25 use `read -r -p`, so the script needs a TTY that the agent's Bash tool does not have. |
| DB-2 | CONFIRMED | diagnosing-bugs:31 says "**Be aggressive. Be creative. Refuse to give up.**" |
| DB-3 | ADJUSTED → Low | The Rules block (lines 13–24) summarises the phases. It is 646 bytes, under the 1 KB Medium bar. |
| IA-1 | CONFIRMED | The HTML-REPORT.md:118 Tone section duplicates the codebase-design glossary rule. It is about 1.3 KB. |
| IA-2 | CONFIRMED | improve-codebase-architecture:23–29 dispatches explorer with the friction questions, and nothing says to paste them or the glossary into the brief. |

Note: the group B reviewer went slightly past "read-only". It curl-fetched the two CDN scripts into the scratchpad to hash them, without running them. It also ran the repo's own `hitl-loop.template.sh` with stdin `/dev/null`. Neither wrote to the repo or HOME.

## Group C

| ID | Verdict | Evidence / note |
|---|---|---|
| CD-7 | CONFIRMED | DEEPENING.md:33 says the old tests "become waste once tests at the deepened module's interface exist — delete them". There is no same-behaviour or green condition. |
| PR-1 | CONFIRMED | UI.md:82 says "under `/prototype/<name>`", but UI.md:35 says "following whatever routing convention… don't invent a new top-level structure". |
| PR-2 | CONFIRMED (Medium by size) | The SKILL.md rules repeated in LOGIC.md and UI.md come to about 1.3 KB in total. |
| PR-4 | ADJUSTED | The line is SKILL.md:27, not :29. It says "ask the user before committing it to a throwaway branch". UI.md:107 and :112 instruct "move the rest onto the throwaway branch" and "lands on the throwaway branch" with no ask. |
| RE-1 (was RS-1) | ESCALATED | research:8 says "Spin up a **background agent**" without naming a type, and brief item 3 makes the agent write the file. The reviewer's fix (general-purpose plus Write) is not enough: in the spec 010 T06 live test, Claude Code refused a subagent's Write of a report file ("Subagents should return findings as text, not write report files"). Fix: the agent returns the Markdown as text, and the main session saves it to the output path. Name the type (general-purpose, or the closest OpenCode equivalent). |
| RE-2 (was RS-2) | CONFIRMED | research:21 holds the injection rule, but it is addressed to the lead. The brief (items 1–4, lines 10–15) never carries it to the agent that reads the web. |

## Group A

The setup-agent-tracker IDs are renamed from `SA-` to `ST-`, so they don't clash with security-audit.

| ID | Verdict | Evidence / note |
|---|---|---|
| ST-1 (was SA-1) | CONFIRMED High | gitlab.md:13 and :56 use `glab issue list -F json`. docs.gitlab.com/cli/issue/list/ (fetched 2026-11-03): "-O, --output string Options: 'text' or 'json'" and "-F, --output-format string Options: 'details', 'ids', 'urls'". Fix: `-O json`. Check every other `-F json` site in gitlab.md against its own command page; per the reviewer, view, mr list and label list still use `-F` for output. |
| ST-2 (was SA-2) | CONFIRMED | gitlab.md:14 says `glab issue note` has "no file or stdin option". docs.gitlab.com/cli/issue/note/: "Without `--message`, opens an editor at a terminal, and otherwise reads the comment from standard input". |
| ST-3 (was SA-3) | CONFIRMED | `gh issue list --help`: "-L, --limit int … (default 30)". github.md:11 has no `--limit`. |
| ST-4 (was SA-4) | CONFIRMED | github.md:10 says `gh issue view <number> --comments`, "filtering comments by `jq`". This matches the 2026-10-30 lead check: piped, `--comments` prints only the comments. |
| ST-5 (was SA-5) / WF-2 | CONFIRMED | github.md:49 says "(`gh api` on the sub-issues endpoint)", with no command. :51 gives the frontier query as prose. |
| TS-1 | CONFIRMED (wording) | to-spec:19 is one sentence carrying four rules. The concern that a parent PRD labelled `ready-for-agent` gets picked up by AFK agents is an owner question, not a defect. |
| TT-1 | CONFIRMED | to-tickets:72 says "Work the **frontier**" (imperative), and :144 says "ready for an agent session to pick up". |
| WF-1 | CONFIRMED | wayfinder:141 says "update or delete those tickets", with no confirm step. |

## Group D

`git status --porcelain` was clean after the run. The reviewer's `npm ci --only=production` probe left nothing in the repo.

| ID | Verdict | Evidence / note |
|---|---|---|
| DK-1 | CONFIRMED High | compose-infrastructure.md:27–28 set `POSTGRES_SHARED_BUFFERS: 256MB` and `POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB`. The official postgres image reads only POSTGRES_PASSWORD, USER, DB, INITDB_ARGS, INITDB_WALDIR, HOST_AUTH_METHOD and PGDATA, so this tuning is silently ignored. |
| DK-3 | CONFIRMED | `npm ci --only=production` appears at dockerfile-patterns.md:39, 198 and 246, and at dockerfile-multistage-and-layers.md:49. |
| MM-1 | CONFIRMED High | migrate-memory:85 says "Each entry: `- [[relative-path|title]] — description`". The code (obsidian_backend.py:414) writes `- [[{stem}]] — {desc}`. |
| MM-2 | CONFIRMED High | migrate-memory:74–79 renames files with no step that rewrites `[[old-stem]]` links. |
| MM-3 | CONFIRMED High | migrate-memory:44–50 merges, moves and deletes `notes/` with no plan or confirm step. This breaks the safety rule. |
| OM-1 | CONFIRMED | obsidian-memory:34 says "OpenCode: the session row's `id`". `_current_session_id` (obsidian_backend.py:26–35) handles only CLAUDECODE / CLAUDE_CODE_ENTRYPOINT. |
| OM-2 | CONFIRMED | obsidian-memory:144 says "chronological list, newest first". The code groups the index by type (obsidian_backend.py:363, 401–416). |
| OM-3 | CONFIRMED | obsidian-memory:161–167 names `memory_backend.py` as "the CLI that implements them". It is repo-developer text, shipped to every user. |
| OM-4 | ADJUSTED (line) | The contradiction is real, but at instructions.py:107, not :93: "Filename is `<session-id>.md`". |
| IN-1 | CONFIRMED | ingest:142 says `memory show <Category>`, and notes.py:104 reads `path / name` (flat layout only). |
| CT-3 | CONFIRMED | chrome-test:24 says "Mint a new UUID … after triaging each report", while :94 says "Optionally mint a NEW `<uuid>`". |
| Others (DK-2, DK-4, DK-5, IN-2, IN-5, IN-7, OM-6, OM-9, MM-4–MM-7, CT-1, CT-2) | ACCEPTED, not individually re-read | Each cites file:line and the code. They are re-read when tickets are written. |

## security-audit

| ID | Verdict | Evidence / note |
|---|---|---|
| SA-01 | CONFIRMED High (owner decision) | validate-findings.cjs:553 says "confirmed finding requires a visible execution observed_result". SKILL.md:33–40 allows execution only inside an OS-enforced sandbox with no network, an allowlisted env, a read-only target and CPU, memory and process limits. Claude Code's built-in sandbox isolates the filesystem and network but sets no resource limits. So on a plain Claude Code setup nothing can reach `confirmed`. A Docker container (`--network none --memory --cpus --pids-limit --read-only`, scratch bind-mount) would meet every control; Docker 29.8.2 is installed here. |
| SA-02 | CONFIRMED | HUNTING.md:223: the critic "receives `architecture.md`, the full coverage ledger including each assignment block map…" pasted into its prompt. |
| SA-03 | ACCEPTED | explorer (Haiku, facts only) is a poor fit for critics and Phase 5 verifiers. Mapping those roles to security-auditor follows decision 6, so I'll apply it by default. |
| SA-04 | CONFIRMED | security-auditor.md:5 says "Run available security tools (brakeman, npm audit…)"; :26 sets a Critical/Warning/Info format; :38 says "End with a summary". All three conflict with the hunter JSON-only contract. |
| SA-08 | CONFIRMED | ATTACK-CLASSES.md and VALIDATION-AND-REPORTING.md have 0 `##` headings. `_check_toc` (skill_validation.py:243–265) fails an empty contents list, and also fails any listed anchor when none is expected. The fix is to promote headings. |
| SA-09 | CONFIRMED | ATTACK-CLASSES.md:35 links CLIENT-SIDE.md a second time, which the validator collapsed, and RECONNAISSANCE.md:84 adds one more. That makes 12 links, not 11. |
| SA-11 | ADJUSTED | The "lead has no Write tool" claim is wrong: `lead.claude.tools` (agents.yaml:14) is dead config, and on Claude Code the main session has every tool. The real gap is our lead text (HARD LIMITS: no Bash beyond read-only, delegate writes), which would push the parent to delegate audit-file writes to coder. The skill should say the parent writes `<output-dir>` itself. |
| SA-05, SA-06, SA-07, SA-10, SA-12, SA-13 | ACCEPTED | They cite file:line. They get re-read when the Req 10 tickets are written. |
