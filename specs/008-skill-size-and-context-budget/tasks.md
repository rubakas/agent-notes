# 008 — Skill Size and Context Budget: Tasks

Ticket index for `spec.md`, which holds the requirements, success criteria and acceptance gates. Every ticket is test-first and ends green.

## Content Fixes (non-blocking for each other, but must complete before T07)

- [ ] **T01 Split docker references into topic files (move-only)** — Split `docker/compose.md` and `docker/dockerfile.md` into topic-focused files ~300–400 lines each (one topic per file, named by topic). Reorganize docker `SKILL.md` to router pattern listing each reference file with a one-line "read when…" summary. Verify no content lost: every `##`/`###` heading and code block from source exists in split output. Req 1, SC-001.

- [ ] **T02 Refresh and split the rails skill against Fizzy** — Check every pattern against Fizzy at pinned commit + `STYLE.md`/`AGENTS.md` (owner supplies source); keep, fix or remove; give each rule a one-line "why". Split 6 reference files into topic-focused files ~300–400 lines each. Add Fizzy-pinned SHA and date to `SKILL.md` header; update config examples to default to Solid Cable/Cache/Queue instead of Redis (note Redis for existing apps only); label ViewComponent as not Fizzy/37signals and name its source; fill gaps (Current/CurrentAttributes, delegated types, multi-tenancy, concerns as facades, Turbo 8 morphing and refresh broadcasts, testing conventions from Fizzy's and Writebook's AGENTS.md); defer conditional style to project RuboCop config; add Sources section to each reference file. Generate and include disposition table (each original section → kept/updated/removed + reason). Req 6, SC-009.

- [ ] **T03 Add table of contents to all reference files > 100 lines** — Add `## Contents` section at the top (before line N, e.g. first 20 lines) of all reference files > 100 lines: the split docker files, the split rails files, plus `triage/AGENT-BRIEF.md`, `improve-codebase-architecture/HTML-REPORT.md`, `prototype/UI.md`, `triage/OUT-OF-SCOPE.md`. TOC format: `## Contents` / `## Table of Contents` heading + list of links to anchors (`[Section](#section)`) or section headings found in the file. Define TOC format precisely in spec.md before coding. Req 1, SC-002.

- [ ] **T04 Shorten descriptions for 7 skills (including rails)** — Edit SKILL.md frontmatter `description` field for rsi, code-review, rails, refactoring-protocol, ingest, docker, codebase-design to ≤ 250 chars. Lead with primary use case in first sentence; preserve trigger keywords for routing discoverability. Run after or with T02 rails refresh. Req 2, SC-003.

- [ ] **T05 Compact the five largest SKILL.md files** — Add a short standing-rules section (≤ 500 tokens, at the top) to chrome-test, wayfinder, obsidian-memory, diagnosing-bugs, ingest SKILL.md files. Move implementation detail or operator/handoff narrative to a reference file if it reduces the SKILL.md below 5,000 tokens. Ensure each file survives compaction (first 5,000 tokens retained). Req 3, SC-004.

- [ ] **T06 Manual verification: reference structure and content preservation** — Docker: verify before/after that every `##`/`###` heading and code block from split output exists. Rails: verify disposition table (T02) against implementation; spot-check major content updates. Req 1, SC-001/SC-009.

## Validation Gate (T07, blocks release)

- [ ] **T07 Extend `agent-notes validate` for skills** — Update `agent_notes/commands/validate.py` to add skill-specific rules (blocked until T01–T06 complete, so the repo passes before the gate is live). Add tests for each rule.

  **Error rules** (block release):
  - `SKILL.md` > 500 lines → error with file path and line count.
  - Estimated tokens in `SKILL.md` (bytes ÷ 3.5) > 5,000 → error with file path and token estimate.
  - `description` frontmatter field > 1,024 chars → error with file path and char count.
  - A reference file (any `.md` in a skill dir) > 100 lines without a `## Contents` or `## Table of Contents` heading in the first N lines → error with file path and line count (define N, e.g. 20 or 5% of file).
  - A reference file that links to another reference file, whether in the same skill or another (e.g. `[link](../other-skill/file.md)` or `[link](../file.md)`). Links to external URLs and to anchors within the same file are fine. → error with source and target paths.
  - A link in `SKILL.md` or a reference file to a file that does not exist (broken relative link) → error with source, target and advice.
  - A frontmatter key outside the allowed set: Claude Code's documented fields (`name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility`) + our own (`group`, `requires_memory`, `triggers`) → error with key name and allowed list.

  **Warning rules** (do not block):
  - `description` > 250 chars → warn with file path and char count.

  **Tests:**
  - A failing-fixture test and a passing-fixture test for each error rule (failing fixtures verify the test fails on pre-change code and passes on fixed code; passing fixtures confirm the rule does not false-positive on valid input).
  - At least one test for the 250-char warning.

  Req 4, SC-005.

## Copy-Mode Reinstall Check (T08)

- [ ] **T08 Copy-mode reinstall check after split** — Blocked by T01 and T02. Functional test (test-first): perform a copy-mode install from a pre-split state, then re-run a copy-mode install after T01 and T02 are complete and both splits are live. Verify no stale old reference files remain in `~/.claude/skills/rails|docker` or `~/.agents/skills/rails|docker`, and no backups of our own files. Uses the spec 007a cleanup to handle renamed files. SC-007.

## Synced Skills Protection (T09, independent)

- [ ] **T09 Protect synced and trash directories** — Independent task, can run any time. Test-first: write the full functional test suite before any implementation.

  **Tests:**
  - Plant a test file in `~/.claude/skills/synced/test-skill/file.txt` with known content; run `agent-notes install` (symlink mode); assert the file is byte-identical and untouched.
  - Repeat for copy mode install.
  - Plant a test file in `~/.claude/skills/.trash/old-skill/file.txt`; run install, reinstall, and uninstall; assert the file survives in all cases.
  - Run `agent-notes doctor --fix`; assert both dirs untouched in symlink and copy mode.
  - Add validation test: a skill directory named `synced` or `.trash` in `agent_notes/data/skills/` fails validation.

  **Implementation** (only where tests fail):
  - Check `install_executor.py` (`_remove_managed_skills`, `_remove_owned`), `install_cleanup.py`, and `diagnostics/_fix.py` to add protection.
  - Update `agent_notes/commands/install.py` uninstall paths to skip `~/.claude/skills/synced/` and `~/.claude/skills/.trash/`.
  - Add validation rule in `validate.py`: a skill directory named `synced` or `.trash` in `agent_notes/data/skills/` fails validation.

  Req 5, SC-006.

## Integration & Closure

- [ ] **T10 CHANGELOG and README updates** — Document the restructuring (docker and rails splits, rails refresh against Fizzy), validation rules, copy-mode reinstall check, and synced-skill protection. Note that spec 007a's cleanup handles renamed reference files on copy-mode reinstall. Link this spec from README.

- [ ] **T11 Full test suite verification** — Run the full test suite (unit + integration). Confirm all new tests from T07, T08, and T09 fail on pre-change code and pass on fixed code. No regression in existing validation, install, uninstall, or reinstall behavior. SC-008 and SC-009.

---

## Blocking Dependencies

```
T01 ──┐
      ├─→ T03 ──→ T06 ──┐
T02 ──┤                 ├──→ (all content/validator done)
      ├─→ T04 ────────┐ │
      ├─→ T05 ────────┤ │         ↓
      └─→ T08 ────────┤ └──→ T07 (copy-mode reinstall; blocked by T01, T02)
                      └──────────────┘
                              ↓
T09 (synced protection; independent, runs any time)
                              ↓
                        T10 (docs; after T07)
                              ↓
                       T11 (full suite; last)
```

**Run order:**
1. T01 (docker split) and T02 (rails refresh) in parallel or sequence (large content tasks).
2. T03 (TOCs), T04 (descriptions), T05 (compaction) in parallel (after T01, T02 as appropriate).
3. T06 (manual verification; after T01, T02).
4. T07 (validator implementation; after T01–T06 are green).
5. T08 (copy-mode reinstall check; blocked by T01 and T02, can run parallel with T07).
6. T09 (synced protection; independent, can run any time).
7. T10 (docs; after T07, T08).
8. T11 (full suite; last).

---

## Acceptance per Ticket

- **T01:** Docker split complete; no content lost; no file > ~400 lines.
- **T02:** Rails refresh complete with disposition table; Fizzy SHA pinned; zero Redis defaults; ViewComponent labelled; gap topics present (Current, delegated types, multi-tenancy, concerns, Turbo 8, testing); each reference file has Sources; RuboCop-defers present; no file > ~400 lines.
- **T03:** All 12+ reference files > 100 lines (docker/rails/other) have TOC section at top; TOC format matches spec definition.
- **T04:** 7 descriptions shortened to ≤ 250 chars (rsi, code-review, rails, refactoring-protocol, ingest, docker, codebase-design); trigger keywords preserved.
- **T05:** 5 SKILL.md files ≤ 5,000 tokens; standing-rules section ≤ 500 tokens at top.
- **T06:** Docker split verified: every `##`/`###` heading and code block from source present. Rails refresh verified against disposition table.
- **T07:** Every new error rule has a failing-fixture and passing-fixture test; tests fail pre-change, pass post-change; repo passes `agent-notes validate`.
- **T08:** Copy-mode reinstall from pre-split to post-split leaves no stale old reference files in rails/docker dirs and no backups.
- **T09:** Synced/trash files byte-identical through install/reinstall/uninstall/doctor cycles in symlink and copy mode; skill named `synced` or `.trash` rejected by validation.
- **T10:** CHANGELOG and README updated (docker split, rails refresh); no broken links; spec 007a cleanup noted.
- **T11:** Full suite passes; no regression; all new tests from T07, T08, T09 green.
