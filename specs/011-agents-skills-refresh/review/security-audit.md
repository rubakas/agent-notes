# security-audit scorecard

Scope: upstream cloudflare/security-audit-skill at c1c8a8c. SKILL.md and all 14 references read in full. report-schema.json parsed (read only). Both validators read for argument shape and exit codes only. Nothing from the clone was executed. Two caveats on checks I did not run: (1) `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` and the OpenCode built-in agent names are unverified, and nothing in the repo mentions the env var. (2) The Claude Code and macOS sandbox claims in SA-01 and SA-06 come from reasoning, not from a test.

**Size** (tokens = bytes / 3.5)
| File | Lines | Bytes | ~Tokens |
|---|---|---|---|
| SKILL.md | 192 | 22,026 | 6,293 |
| HUNTING.md | 251 | 22,446 | 6,413 |
| VALIDATION-AND-REPORTING.md | 186 | 17,843 | 5,098 |
| RECONNAISSANCE.md | 156 | 15,902 | 4,543 |
| ATTACK-CLASSES.md | 130 | 15,695 | 4,484 |
| WEB-PROTOCOL-AND-AUTH.md | 105 | 12,300 | 3,514 |
| AI-AND-LLM.md | 83 | 10,617 | 3,033 |
| MEMORY-SAFETY-AND-BINARY.md | 101 | 10,513 | 3,004 |
| DESKTOP-MOBILE-AND-LOCAL-IPC.md | 89 | 8,739 | 2,497 |
| CLIENT-SIDE.md | 83 | 8,594 | 2,455 |
| CLOUD-AND-DEPLOYMENT.md | 86 | 8,291 | 2,369 |
| DATA-ISOLATION-AND-LIFECYCLE.md | 84 | 7,798 | 2,228 |
| PROTOCOLS-RPC-AND-MESSAGING.md | 81 | 7,483 | 2,138 |
| RESOURCE-EXHAUSTION-AND-AVAILABILITY.md | 78 | 7,476 | 2,136 |
| SUPPLY-CHAIN-AND-RELEASE.md | 73 | 7,258 | 2,074 |
| report-schema.json | 461 | 14,494 | 4,141 |
| validate-findings.cjs / validate-coverage-ledger.cjs | 773 / 872 | 28,806 / 33,522 | not loaded |
| *.test.cjs (2 files) | 652 / 740 | 26,384 / 28,483 | not loaded, never referenced by the skill |

Markdown total is 182,981 B (about 52k tokens). SKILL.md description is 373 B.

SKILL.md section sizes in bytes:
- Full audit planning, lines 88–135: 7,503.
- Promotion procedure, lines 68–82: 2,208.
- Write isolation, lines 54–86: 4,018.
- Core principles, lines 136–166: 3,107.
- Anti-patterns, lines 181–192: 811.

After Req 10c moves lines 88–135, SKILL.md is 14,523 B (about 4,149 tokens). With 10d, 10f, 10g and 10h added, I estimate about 16.4 KB (about 4,700 tokens), which stays under the 5,000 cap.

**Goal as an LLM reads it**
- **Guidance mode.** Goal: answer a security question, or review specific code for boundary-crossing vulnerabilities, using only the relevant parts of the skill. Input: the user's question or named code or scope. Output: an answer or findings in chat; no output directory and no files (SKILL.md:14). Stops when: the question is answered. The skill never says this last point; it is implicit.
- **Full-audit mode.** Goal: find source-grounded vulnerabilities that cross a real trust boundary, independently verify them, and report them with the smallest fix (SKILL.md:8). Input: the target repo root, plus profile, scope, budget and any prior runs in `~/security-audit-skill/<repo>/`. Output: `<output-dir>` containing run-metadata.json, architecture.md, coverage-ledger.json, findings.json, REPORT.md, FINDINGS-DETAIL.md and NEEDS-VALIDATION.md. Stops when (SKILL.md:179): (a) all Phase 6 files are written and both validators pass, or (b) `run_status: "incomplete"` is recorded with its reason and the gap is disclosed.

**Scores**
- G1 minor — SKILL.md:3: 373 B; opens with a noun phrase ("Security guidance and vulnerability review…") and says "Use for", not "Use when". Triggers are specific, but the main use case (audit or pen test) comes last.
- G2 pass — SKILL.md:12–17 and :179 state mode, outputs and stop condition. Full-audit detail needs 3–4 files read.
- G3 fail — SKILL.md:1–4: no `disable-model-invocation` despite a large fan-out and writes outside the repo (SKILL.md:51); no `argument-hint`. Overlaps: built-in `security-review` skill, `security-auditor` agent, `af:review`, `dual-review`, `review`, `code-review`.
- W1 minor — HUNTING.md:37,43,52,58,71 have all-caps lead-ins. "ANY" is in 10 Validation-rules headings (e.g. AI-AND-LLM.md:76). "Never" appears 47 times (SKILL 14, HUNTING 14, VALIDATION 11, RECON 4, ATTACK 2, CLIENT 1, RESOURCE 1), almost all legitimate safety rules.
- W2 minor — ATTACK-CLASSES.md:128 ("thorough and literal. Check every item."), :37 ("Do not stop at the obvious"), RECONNAISSANCE.md:41 ("Be complete").
- W3 minor — mixed terms: final-clean / final / post-wave critic; "final verifier" (VALIDATION.md:145) / Phase 5 verifier; "lead" (VALIDATION.md:163,182) / candidate; "Task tool" / `subagent_type`.
- W4 pass — no time-sensitive statements.
- W5 pass — default profile `standard` (SKILL.md:109) and a default output directory (:51).
- W6 minor — minimum 8 agent calls (4 recon, 1 hunter, 1–2 critics, 1 verifier, 1 Phase 5). Real runs are dozens. This conflicts with "keep spawn counts low", but it is opt-in and has a budget gate. There is no user checkpoint on the estimated agent count unless a budget is set (SKILL.md:132 only warns when a budget can't fund the run).
- S1 fail — 192 lines (pass), but 6,293 tokens against the 5,000 cap. About 4,149 after 10c.
- S2 fail — SKILL.md links 4 of 14 references (SKILL.md:82,94,172–174). The 10 companions are orphans. There are 12 reference-to-reference markdown links (ATTACK-CLASSES.md:9,11,13,15,17,19,21,23,25,27,35 and RECONNAISSANCE.md:84).
- S3 fail — HUNTING 251, VALIDATION 186, RECON 156, ATTACK-CLASSES 130, WEB-PROTOCOL 105 and MEMORY-SAFETY 101 lines, none with a Contents. ATTACK-CLASSES.md and VALIDATION-AND-REPORTING.md cannot pass our validator at all (SA-08).
- S4 minor — six numbered phases (SKILL.md:170–177) and strong loops (validators at VALIDATION.md:111–118; critic waves at HUNTING.md:221–251). There is no copyable checklist for a run spanning dozens of calls and 7 files.
- S5 minor — script use is explicit (`node <skill-dir>/validate-*.cjs <path>` at RECON.md:156 and VALIDATION.md:111–114). The Node prerequisite is stated nowhere.
- S6 minor — JSON contracts are shown (RECON.md:107–133; HUNTING.md:170–206, 228–243), but there is no filled-in ledger unit or assembled hunter prompt. There is one `canonical_refs` sample.
- S7 pass — descriptive names, forward slashes.
- E1 minor — ATTACK-CLASSES.md:29–90 (generic OWASP classes), :113–127 and :92–109 are largely known to Claude. They are by design the payload for hunters; leave them.
- E2 fail — the promotion procedure appears three times: SKILL.md:68–80, HUNTING.md:101–135 and VALIDATION.md:50–84 (word-level identical apart from backticks, so SKILL.md:82's "same rules, same order" claim is true). Other duplication: prior-run rules (SKILL.md:94–105 and RECON.md:59–71), the sandbox-control list in 5 places, the attempts/reassign rule (RECON.md:139 and HUNTING.md:247), and the final classification rule in every companion.
- E3 fail — SKILL.md lines 44–135 and 168–192, about 14 KB of 22 KB, are full-audit only, though guidance mode is the default.
- E4 — about 18 KB (about 10% of the markdown) is avoidable; see SA-15 to SA-20 below.
- E5 fail — 373 B against the 250 target, with the key use case last.
- A1 pass — no agent-notes subcommands are named.
- A2 pass — the only CLI is `node <file> <abs-path>`: exit 0 prints PASS, exit 1 prints FAIL, and no argument prints usage and exits 1 (validate-findings.cjs:704–771, validate-coverage-ledger.cjs:809–870). The validator loads `report-schema.json` from `__dirname`, so the skill directory must stay intact.
- A3 fail — `research` and `general` are not real agent names here. Even after 10f there are gaps (SA-03, SA-04, SA-05).
- A4 minor — "Task tool" is generic (SKILL.md:24); no Claude Code or OpenCode tool names appear.
- A5 minor — all 14 linked or named files exist, and the skill correctly pastes blocks into briefs because subagents don't inherit skills. Five `SKILL.md` pointers go stale after 10c (SA-07).
- A6 pass — validator limits and the canonical-ID algorithm match the code (see accuracy log). Two items I did not check against code: the state table (RECON.md:143–150) and the "2,000–5,000 realistic units" estimate. run-metadata.json has no schema or validator.

Per-reference W/S/E: the 10 companions share one shape. W1/W2/W4 pass; S2 pass (they use backticks); S3 fails only for MEMORY-SAFETY (101 lines) and WEB-PROTOCOL (105); E2 fails on the duplicated final classification bullet. HUNTING, RECON and VALIDATION carry the E2 duplication and the all-caps lead-ins above.

**Req 10 sufficiency**
- **10b — insufficient.**
  - `disable-model-invocation: true` removes the only auto-trigger for guidance mode, whose purpose is "security questions" (SKILL.md:3,12–14). That is an owner decision to make knowingly.
  - There is no `argument-hint`.
  - The `security-review` skill and the `security-auditor` agent remain name overlaps.
  - A 229-character draft that fits: "Finds and validates security vulnerabilities in a codebase and writes a verified report. Use when asked for a security audit, pen test, full or end-to-end security review, vulnerability hunt, or focused security guidance on code."
  - `group: process` matches code-review and rsi.
- **10c — insufficient.**
  - Ranges are right (88–135 is 7,503 B; 68–81 is 2,208 B, but include line 82 in the move).
  - After the planning move SKILL.md is about 4,149 tokens, under the 4,800 trigger, so the promotion move would not fire. Move it unconditionally, or replace it (SA-06).
  - Five `SKILL.md` pointers go stale (SA-07).
- **10d — insufficient by one.** The count is 12, not 11: RECONNAISSANCE.md:84 is the 12th link (SA-09). Linking the 10 companions from SKILL.md is right.
- **10e — insufficient for 2 of 6 files.**
  - ATTACK-CLASSES.md and VALIDATION-AND-REPORTING.md have zero `##` headings.
  - Our `_check_toc` (skill_validation.py:243–265) requires the Contents to list every `##` heading in order, so these two files fail with any `## Contents`.
  - The other four are fine. Their `##` headings contain `(subagent_type: \`general\`)`, which ends up in the anchors.
- **10f — insufficient.**
  - Write/Edit: no phase needs it for agents.
    - Hunters and verifiers return JSON (HUNTING.md:9,170; VALIDATION.md:42,143).
    - Recon agents and critics are read-only (RECON.md:7; HUNTING.md:223).
    - The parent writes all shared files (SKILL.md:56–66).
    - The only agent-side writes are by target-controlled processes into `scratch/` (SKILL.md:37,40; HUNTING.md:85–86; VALIDATION.md:7), and those go through Bash in a sandbox.
    - Without a sandbox there are no scratch writes, so the `agents/<id>/scratch|artifacts` directories (HUNTING.md:9, RECON.md:5) are created for nothing.
    - Write/Edit denial is not a write-isolation control; Bash can still write.
  - The mapping misses SA-01, SA-03, SA-04, SA-05, SA-11 and SA-12.
- **10g — sufficient.** State it once centrally, with the cap value: "wherever a file says 'in parallel', launch in batches of at most 5". RECON.md:7 (4 agents) fits. VALIDATION.md:122 ("one per record, in parallel") and hunter waves need batching. The env var is unverified.
- **10h — insufficient.** It covers only the grep at ATTACK-CLASSES.md:113 (SA-10).

**Findings**
| ID | Sev | Tag | Rubric | file:line | Problem | Fix | Bytes saved |
|---|---|---|---|---|---|---|---|
| SA-01 | High | req10-gap | A3, safety | SKILL.md:33–40,86; HUNTING.md:71–80,150; ATTACK-CLASSES.md:7; schema `execution.observed_result` | Claude Code gives no verifiable OS sandbox (macOS can't enforce memory or process limits). The skill then forbids executing target code, but `confirmed` requires a bounded local observed result, so nothing can be `confirmed`. Hunters hold Bash, so only prose stops them running untrusted target code. Each hunter is told to judge sandbox availability itself, and it can't. The literal `execution_policy: "sandboxed-source-and-local-only"` (SKILL.md:86) becomes false. | "On Claude Code no OS sandbox is assumed. Unless the user names a sandbox wrapper command, set `execution_policy: \"source-only\"`, run nothing from the target, and put `execution: disabled` in every hunter and verifier brief. Record would-be-confirmed items as `needs_validation` and tell the user before wave 1." Owner decision: allow source-only `confirmed` instead? | +0.6 KB |
| SA-02 | Medium | req10-gap | A3, E3 | HUNTING.md:223 | The coverage critic gets "the full coverage ledger" in its prompt. The ledger is up to 5 MiB (RECON.md:156). 300 units at about 1.1 KB each is about 330 KB, about 95k parent output tokens (my estimate). | "It receives the absolute paths of `architecture.md` and `coverage-ledger.json` and reads them." | ≈0 B in the skill, avoids ≈95k output tokens |
| SA-03 | Medium | req10-gap | A3 | HUNTING.md:223; RECON.md:22–33; VALIDATION.md:122–149,145; explorer.md | `research` mapped to explorer (Haiku, "No analysis or recommendations. Just facts.") for roles that need judgment: coverage critic, recon 1b, and Phase 5 record verifier (severity separation, "merely moving trust"). VALIDATION.md:145's replacement verifier must reproduce results, which needs Bash and doesn't fit `research` either. | Map `research` to explorer only for recon 1a, 1c and 1d. Map critics, recon 1b and every Phase 5 verifier to `security-auditor`. Cost is a few extra Sonnet calls, offset by fewer discarded malformed results. | n/a |
| SA-04 | Medium | req10-gap | A3, W3 | HUNTING.md:170; VALIDATION.md:42,89,143; security-auditor.md; explorer.md | Skill demands "exactly one JSON object, no surrounding prose" and discards malformed results without repair, burning budget. security-auditor's body mandates a Critical/Warning/Info format and an "End with a summary". explorer has its own Output format and Reporting sections. security-auditor step 1 says to run `npm audit` (network). | Add to the 10f text: "The brief's output contract overrides the agent's default report format and tool steps. Open every brief with: 'Ignore your default report format; reply with only the JSON object. Do not run network audit tools.'" | +0.2 KB |
| SA-05 | Medium | req10-gap | A3 | RECONNAISSANCE.md:17,53–54 | Explorer (Read, Grep, Glob) is asked for host facts: missing local toolchains (1a#6), whether the platform can enforce sandbox controls (1d#6), whether trusted promotion code exists (1d#7). These need `command -v`, `uname` or host knowledge, so it will guess. No recon prompt asks for `git log`; git probes are parent-side (SKILL.md:50–52). | Delete 1a#6 and 1d#6–7 from the explorer prompts. The parent probes with Bash (`uname -s`; `command -v bwrap sandbox-exec docker node python3`) and records the verdict, feeding SA-01. | −0.7 KB |
| SA-06 | Medium | req10-gap | A4, (b) | SKILL.md:68–80 (copies: HUNTING.md:101–135, VALIDATION.md:50–84) | The procedure assumes capabilities a Claude Code main session lacks. It needs descriptors retained across steps, but each Bash call is a new process. It needs `openat`/`fstat`, but no helper script ships and Node `fs` has no dir_fd. Read/Write follow symlinks. "Trusted parent-side code" is just the parent plus Bash. | "On Claude Code: with execution disabled there is nothing to promote; skip this section. With a user-supplied sandbox, after the hunter exits promote each allowlisted file in one `python3 -I` call (`os.open` with `dir_fd`, `O_NOFOLLOW\|O_NONBLOCK`, `os.fstat` regular file, `st_nlink == 1`, size cap). Never use Read, Write or `cp`." | −1.5 KB net if the 11-step list is replaced |
| SA-07 | Medium | req10-gap | A5, S2 | RECONNAISSANCE.md:5,57; HUNTING.md:166,251; VALIDATION.md:93; SKILL.md:82 | After 10c, five backticked `SKILL.md` pointers (budget gate, host procedure) go stale. SKILL.md:82 ("HUNTING.md and VALIDATION… carry this procedure") is orphaned. | Repoint to `PLANNING.md` (budget) or `WRITE-ISOLATION.md` (promotion). Move line 82 together with 68–81. | 0 |
| SA-08 | Medium | req10-gap | S3 | ATTACK-CLASSES.md (0 `##`), VALIDATION-AND-REPORTING.md (0 `##`); skill_validation.py:243–265 | The TOC check needs every `##` heading listed. Files with none fail even with a `## Contents`. | Promote the bold class names in ATTACK-CLASSES.md and the `### Phase N` headings in VALIDATION to `##` (RECON.md:94 allows "as a heading"). Strip `(subagent_type: \`general\`)` from the 33 H2 headings, which shortens the anchors. | 0 |
| SA-09 | Low | req10-gap | S2 | RECONNAISSANCE.md:84 | The link count is 12, not 11. RECON.md:84 is the 12th. | List RECON.md:84 in 10d. | 0 |
| SA-10 | Medium | req10-gap | (f) credentials | ATTACK-CLASSES.md:103,113,118; schema `execution.payloads` (minItems 1); VALIDATION.md:171–178 | (i) `git log -p` or `-S` for "secrets committed then removed" prints secret values into context. (ii) The grep echoes matched values from ordinary source files, and a hardcoded-secret finding can persist the value in findings.json or FINDINGS-DETAIL.md. (iii) Our "path contains token/secret/credential" rule would make `auth/token.ts` unreadable in an auth audit. (iv) The credential-guard hook blocked my own grep that named credential files. | "Never print, quote or store a secret value: cite file:line and secret type only, and use `grep -l/-c`. In history use `git log --stat --diff-filter=D -- <path>`, never `-p`. Check credential files with `test -f` and `git ls-files`/`git check-ignore`. A credential file is a file holding secret values; code that handles tokens is source." | +0.5 KB |
| SA-11 | Medium | req10-gap | (f) orchestration | SKILL.md:17,56–66,175; agents.yaml:14; CLAUDE.md HARD LIMITS/Phase 0 | The skill needs the parent to Write 7 files and run `node`/`mkdir`. Our lead has no Write tool and its limits forbid that Bash, so it might delegate to `coder`, which breaks "parent is the only writer". SKILL.md:17's mode question also duplicates our Phase 0 plan gate. | "Files under `<output-dir>` are audit artifacts outside the project. The parent writes them itself and runs the validators; do not delegate to coder. Ask the mode, profile, scope, budget and output-dir question once, inside the plan, and state the estimated agent count before wave 1." | +0.4 KB |
| SA-12 | Low | req10-gap | A4 | SKILL.md:24 | 10f names only Claude Code. The skill installs unchanged to OpenCode (`task` tool). security-auditor's OpenCode bash allowlist is brakeman, bundler-audit, `npm audit*`, grep and `git log*` (agents.yaml:62–73), so hunters there can run nothing locally. I did not verify OpenCode's built-in agent names. | "Task tool: `Agent` on Claude Code, `task` on OpenCode." | +0.1 KB |
| SA-13 | Medium | req10-gap | G3, (e) | SKILL.md:12–17,172–177 | Guidance mode never says which files to read: ATTACK-CLASSES.md and the companions are named only in the full-audit workflow. With 10b, a bare `/security-audit` can mean either mode and there is no argument. | "Guidance mode: read ATTACK-CLASSES.md and the one companion matching the target's boundary; apply Universal execution safety; create no files." Add `argument-hint: "[guide\|audit] [path]"`. | +0.3 KB |
| SA-15 | Medium | optional | E2 | HUNTING.md:99–136; VALIDATION.md:48–85 | The promotion block is copied into every hunter and verifier prompt, yet it says "Reference only for you… you never perform them". It costs 2.27 KB per call for nothing. | Drop the block from the hunter and verifier prompt lists (HUNTING.md:20, VALIDATION.md:7,48). Keep one copy. | 4.5 KB static; 2.3 KB per agent call |
| SA-16 | Low | optional | E2 | SKILL.md:94–105 vs RECONNAISSANCE.md:59–71 | The prior-run carry/revalidate rules are near-duplicates (2.2 KB and 2.1 KB). | Keep PLANNING.md as the source. RECON keeps only its `prior_status` link bullets. | ≈1.5 KB |
| SA-17 | Low | optional | E2 | SKILL.md:35–38; RECON.md:53; HUNTING.md:71–76,159–166; VALIDATION.md:14–17 | The sandbox-control list appears 5 times. HUNTING.md:159–166 (1,393 B) restates the Universal safety rules. | Delete HUNTING.md:159–166; point at the single list. | ≈2.2 KB |
| SA-18 | Low | optional | E2 | Validation rules, last item of each companion (AI-AND-LLM.md:83, CLIENT-SIDE.md:83 … WEB-PROTOCOL-AND-AUTH.md:105) | The final "Return `confirmed`… `needs_validation`…" item repeats the Core discipline's last bullet (e.g. AI-AND-LLM.md:17), and both land in the same hunter prompt. | Remove the Validation-rules copy in the 10 companions. | 2.1 KB |
| SA-19 | Low | optional | E1, E2 | 53 occurrences in 11 files (SKILL.md:27, ATTACK-CLASSES.md ×9, companions ×4–5 each) | Every annotation is `general`, so it carries no information, and after 10f it is misleading (`general` is not `general-purpose`). Touching 53 lines raises the re-sync cost. | `sed -i '' 's/ (subagent_type: \`general\`)//'`. Or leave it and rely on the 10f mapping. | 2,765 B |
| SA-20 | Low | optional | E2 | SKILL.md:183–192; RECON.md:139 vs HUNTING.md:247; SKILL.md:123,128,130,132 vs HUNTING.md:251, RECON.md:57 | Anti-patterns restate earlier rules (811 B). The attempts rule is duplicated (about 1.2 KB). The budget-reserve rule appears 4+ times (about 1.5 KB). | Delete the anti-pattern list; keep one copy of each rule in PLANNING.md. | ≈3.5 KB |
| SA-21 | Low | optional | W1, W2 | HUNTING.md:37,43,52,58,71; ATTACK-CLASSES.md:128; RECON.md:41 | All-caps lead-ins and the "thorough and literal" filler. | Sentence-case the five lead-ins; delete ATTACK-CLASSES.md:128. | ≈0.2 KB |
| SA-22 | Medium | optional | E3 | HUNTING.md:13–25,27–97,168–213 | The "copy verbatim" rule makes the parent emit about 12.4 KB of static boilerplate plus about 5.7 KB of minified schema branches per hunter. At 40 hunters that is over 200k parent output tokens (my estimate). Hunters have Read and the skill-dir path is known. | Give hunters `<skill-dir>/HUNTING.md` section names and the `FILE.md#block` references already in the ledger; keep only the per-unit parts inline. | ≈15 KB per hunter prompt |
| SA-23 | Low | optional | S5 | RECON.md:94–102,139; HUNTING.md:217 | The parent hand-derives hundreds of percent-encoded `coverage_id` values, sorts them and rewrites the ledger on every update. `canonicalCoverageId` is exported (validate-coverage-ledger.cjs:368–375) but the skill never says to use it. | Say the parent computes IDs and applies updates with a small script that calls the exported function. | n/a |
| SA-24 | Low | optional | S5 | validate-coverage-ledger.cjs:394–398; HUNTING.md:217 | The validator checks only that an artifact path has the right shape, not that the file exists. | Add "`test -f` each cited artifact before accepting a local check." | +0.1 KB |
| SA-25 | Low | optional | W1 | SKILL.md:179 | "Do not end the run before one of exactly two terminal states… Never stop mid-phase" conflicts with a user stop request. | Append "unless the user stops the run." | +0.03 KB |
| SA-26 | Low | optional | S5, A2 | RECON.md:156; VALIDATION.md:111 | Node is unstated, and terminal state (a) is unreachable without it. | "If `node` is missing, record `run_status: \"incomplete\"` with reason `validators_unavailable`." | +0.1 KB |
| SA-27 | Low | optional | E5 | the two `*.test.cjs` files | 54.9 KB of tests are not referenced by the skill. | Exclude them when vendoring (no text edit). | 54.9 KB on disk, 0 tokens |
| SA-28 | Low | optional | (f) | ATTACK-CLASSES.md:120 | "Known CVEs in the dependency tree (check lockfiles)" cannot be done offline. `npm audit` would send the package list to a registry, against RECON.md:5. | "Compare lockfile versions to advisories only if a local advisory source exists; otherwise `needs_validation`." | +0.1 KB |

(f) summary:
- No AI attribution: the skill adds none; grep for generated/co-authored/anthropic terms found nothing. REPORT.md:159 ("agents spent versus planned") and the agent IDs in artifact paths reveal tooling only if the output is committed, which is possible via SKILL.md:51. Not a violation.
- Confirm before destructive or outward actions: the skill forbids live probes, publishing and installs (SKILL.md:42). Gaps are SA-11 (cost checkpoint) and SA-28.
- Credentials: SA-10.

Counts: 28 rows in the table (SA-14 not used), 13 `req10-gap` (SA-01 to SA-13), 15 `optional`.

**Accuracy log**
- SKILL.md:3 description → `wc -c` → 373 B → OK
- SKILL.md frontmatter has only `name` and `description` → Read → OK
- Linked files in SKILL.md and the 10 companions exist → `ls`, size listing → OK
- RECONNAISSANCE.md:156 ledger-validator limits (5 MiB, 10,000 units, 1,000 per collection, 64 depth, 500,000 values, 100 errors) → validate-coverage-ledger.cjs:13–21 → OK. The "2,000–5,000 units" estimate was not verified.
- VALIDATION.md:118 findings-validator limits (5 MiB, 1,000 findings, 64 depth, 100 errors) → validate-findings.cjs:42–49 → OK
- Validator CLI: one path argument; exit 0 PASS, exit 1 FAIL or no argument; files opened O_NOFOLLOW|O_NONBLOCK, regular file only → `run()` read in both files → OK
- RECON.md:94–102 canonical ID (NFC, UTF-8 percent-encoding with `A-Za-z0-9-._~` unreserved, uppercase `%HH`, `::` join, optional lifecycle) → validate-coverage-ledger.cjs:354–375 → OK
- RECON.md:100–102 lexicographic sort → validate-coverage-ledger.cjs:~800 → OK. The state table (RECON.md:143–150) → not traced → unverified.
- SKILL.md:82 "identical block, same order" → normalized word diff of SKILL.md:68–80 against HUNTING.md:105–135 and VALIDATION.md:54–84 → OK
- 53 occurrences of `(subagent_type: \`general\`)`, all `general` → `grep` → OK
- 10d "11 links" → `grep` of markdown links → WRONG (12)
- 10c ranges 88–135 and 68–81 → `sed`/`wc` → OK (7,503 and 2,208 B; line 82 is also needed)
- 10c 4,800-token trigger → arithmetic (22,026 − 7,503 = 14,523 B ≈ 4,149 tokens) → would not trigger
- 10e "every reference over 100 lines" → `_headings` helper from our validator → 6 files; 2 have no `##` → partly WRONG
- security-auditor tools → agents.yaml:55–73 and security-auditor.md → OK. Your stated tool list (Read, Grep, Glob, Bash, WebFetch) matches the Claude config; I took it from the spec, not from the repo.
- explorer tools and persona → agents.yaml:75–87 and explorer.md → OK
- lead tools → agents.yaml:14 → OK (no Write)
- Schema branch sizes (confirmed 3,948 B, needs_validation 1,727 B, rejected 1,420 B, minified) → python parse → OK
- `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` → repo grep, no hits → unverified (taken from your brief)
- OpenCode built-in agent names → not checked → unverified

**Verdict:** The skill is usable but cannot be vendored with Req 10 as written. Req 10 covers packaging and wording well, but it misses the Claude Code dead end (no sandbox means no `confirmed` findings and prose-only protection against running target code), plus host probes sent to a tool-limited explorer and critic prompts that paste the whole ledger. It also misses two files that can never pass our TOC check, five stale `SKILL.md` pointers, and credential/git-history conflicts: 13 req10-gap items to add before vendoring.
