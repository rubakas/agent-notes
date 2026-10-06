# 008 — Skill Size and Context Budget

**Feature Branch**: `develop` (direct)

**Created**: 2026-10-06

**Status**: Approved 2026-10-06

**Input**: "anthropic updated the rules for skills, get the latest updates from it and findout what we need to do with our big skills" (user, 2026-10-06); "write spec 008 with all items, skip uploadability" (user, 2026-10-06)

## Investigation

Method: fetched Anthropic's current skill rules from code.claude.com/docs/en/skills.md, platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices.md, and CHANGELOG 2.1.261 / 2.1.105 (2026-10-06). Measured all 25 skills in `agent_notes/data/skills/` by line count, token estimate (bytes ÷ 3.5), and reference file structure. Verified against the live code in `agent_notes/commands/build.py`, `validate.py`, and `scripts/release`.

### Anthropic's Current Rules

**Skill lifecycle and compaction:**
- Invoked `SKILL.md` content enters the conversation once and is not re-read on later turns.
- After auto-compaction, Claude Code re-attaches the most recent invocation of each skill, keeping only the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens, filled from the most recently invoked, so older skills can be dropped on overflow.
- Guidance: put the most important instructions near the top of `SKILL.md`.

**Skill descriptions and listing budget:**
- Each turn Claude sees a listing of all skill names + descriptions, capped at 1% of the context window.
- Each entry's `description` + `when_to_use` is cut at 1,536 chars per skill (raised in CHANGELOG 2.1.105 from prior 250 chars).
- On overflow the descriptions of the least-used skills are dropped (names kept).
- `/skill-doctor` (CHANGELOG 2.1.261) shows unused skills and their context cost. `/doctor` shows the listing cost.

**File size and structure:**
- Keep `SKILL.md` under 500 lines.
- Move detailed reference material to separate files, one level deep from `SKILL.md`.
- For reference files longer than 100 lines, include a table of contents at the top.
- Nested references may be previewed with `head -100`.

**Frontmatter:**
- Upload-compatible keys (accepted by claude.ai, Skills API, `package_skill.py`): `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
- Claude Code accepts `metadata` (does not act on it).
- Other keys hard-fail on upload paths; Claude Code accepts every field in its documented frontmatter table.
- `name` ≤ 64 chars, lowercase/digits/hyphens, no "anthropic"/"claude"; `description` ≤ 1,024 chars (spec).

**Synced skills:**
- Claude Code syncs claude.ai skills into `~/.claude/skills/synced/` and keeps removed personal skill folders in `~/.claude/skills/.trash/`.
- It does not move or delete folders you create.

### Our Skills Today (measured 2026-10-06)

**SKILL.md sizes:**
- All 25 skills under 500 lines, all under ~5k tokens.
- Largest by line count and tokens: chrome-test 268 lines / ~3.6k tokens; wayfinder 128 / ~3.3k; obsidian-memory 200 / ~2.8k; diagnosing-bugs 135 / ~2.4k; ingest 171 / ~2.0k.

**Reference files — the big ones (over 100 lines, lacking table of contents):**
- **Rails skill** (6 reference files): `rails/infra.md` 1,121 lines / ~6.0k tokens / 6 sections; `rails/models.md` 1,105 / ~7.2k / 5 sections; `rails/controllers.md` 770 / ~4.7k / 4 sections; `rails/frontend.md` 742 / ~4.5k / 3 sections; `rails/views.md` 620 / ~3.8k / 4 sections; `rails/testing.md` 566 / ~3.3k / 3 sections.
- **Docker skill** (2 reference files): `docker/compose.md` 882 / ~5.8k / 15 sections; `docker/dockerfile.md` 667 / ~4.7k / 14 sections.
- **Other skills** (4 reference files): `triage/AGENT-BRIEF.md` 207 / ~2.3k; `improve-codebase-architecture/HTML-REPORT.md` 123 / ~1.9k; `prototype/UI.md` 112 / ~2.0k; `triage/OUT-OF-SCOPE.md` 105 / ~1.3k.
- Total: 12 reference files > 100 lines, NONE with a table of contents. One read of the largest (rails/models.md) costs up to ~7k tokens.

**Reference file structure:**
- All references are one level deep from their skill's `SKILL.md`. Nothing outside the rails and docker skill directories links to their reference files (git grep, excluding specs/).

**Descriptions — over-budget for the listing:**
- Total: ~5,460 chars across 25 skills, sharing the 1% listing budget with every other installed skill on the user's system.
- Over 250 chars (target for compaction): 7 skills: rsi 492, code-review 417, rails 415, refactoring-protocol 304, ingest 298, docker 273, codebase-design 265.

**Frontmatter keys in use:**
- Standard across all 25: `name`, `description`.
- Non-standard, custom to us: `group` (all 25), `disable-model-invocation`, `argument-hint`, `requires_memory`, `triggers`.
- Spec 001 decision #3 (still open): migrate custom keys under `metadata` vs. accept non-upload-ability.

**Build and validation:**
- `agent_notes/commands/build.py` `copy_skills()` copies each skill dir as-is to `dist/skills/<name>/` (no frontmatter rewrite).
- `agent_notes/commands/validate.py` (skills section ≈ lines 100–133) checks only required `name`/`description`, name regex, and name == directory.
- Agents have line limits (300; lead 500). `scripts/release` runs `agent-notes validate` in pre-flight, so new validation errors block a release.

### Rails skill provenance and drift

The rails skill was distilled from Fizzy (github.com/basecamp/fizzy, O'Saasy license, MIT-like). Fizzy is Basecamp/37signals' house Rails codebase tracking Rails main (8.2 alpha); the latest released Rails is 8.1.4. Skill examples match Fizzy's `app/models/card/*` concerns. Fizzy has `STYLE.md` (house style guide) stating "we prefer expanded conditionals over guard clauses" and `AGENTS.md` for agent handoff. Fizzy's PR history reviewed by Jorge Manrubia and DHH.

**Fizzy's stack (Gemfile across 153 changes since 2024-06-21):** Solid Queue, Solid Cache and Solid Cable (since at least 2025-04); Redis only in the first commit; view_component never appears.

**Drift in our skill:**
- `views.md` teaches ViewComponent (15 mentions, also in `SKILL.md`), added from a non-37signals source by the owner.
- `frontend.md:572-581` configures Action Cable with Redis adapter.
- `infra.md` (~lines 559, 670-698, 752) runs Redis in Kamal.
- Solid Cable, Solid Cache, Solid Queue never mentioned.
- Delegated types never taught.
- `Current` (CurrentAttributes) used throughout but never defined.

**Sources verified (HTTP 200 on 2026-10-06):** dev.37signals.com/good-concerns/, /vanilla-rails-is-plenty/, /the-rails-delegated-type-pattern/ (dated 2025-12-19), /a-vanilla-rails-stack-is-plenty/ (2024-12-12).

## Functional Requirements

### Requirement 1: Restructure docker references (move-only)

Split the 2 docker reference files into topic-focused files of roughly 300–400 lines per file. Each topic becomes a separate reference file named by topic. Keep every reference one level deep from the docker skill's `SKILL.md`. The `SKILL.md` becomes a short router listing every reference file with a one-line "read when…" summary. Content is moved, not rewritten or dropped — verify by before/after check that every original `##`/`###` heading and code block still exists somewhere in the skill. (Rails restructuring is covered in Requirement 6.)

**Acceptance:**
- No docker reference file exceeds ~400 lines (estimated ~2.8k tokens).
- Every original heading and code block from the source is present in the split output.
- No guidance is added, removed or rewritten; only router lines in `SKILL.md` and tables of contents are new.

### Requirement 2: Shorten descriptions

Every skill description ≤ 250 chars. Lead with the key use case in the first sentence. Keep the trigger keywords that route requests. Applies to 7 skills: rsi (492 chars), code-review (417), rails (415), refactoring-protocol (304), ingest (298), docker (273), codebase-design (265).

**Acceptance:**
- All 25 skill descriptions are ≤ 250 chars.
- Trigger keywords preserved for discoverability.
- First sentence names the primary use case.

### Requirement 3: Compaction-proof the five largest SKILL.md files

The must-hold rules and decisions for chrome-test, wayfinder, obsidian-memory, diagnosing-bugs, and ingest go in a short section at the top of each file, phrased as standing instructions (not historical context or implementation detail). Operator/handoff detail in chrome-test's SKILL.md may move to a reference file. Each file stays well under 5,000 tokens to survive compaction and re-attachment.

**Acceptance:**
- Each of the 5 SKILL.md files is ≤ 5,000 tokens (estimated bytes ÷ 3.5).
- A short top section (≤ 500 tokens) holds standing rules and decisions.
- The file can survive Claude Code's compaction (first 5,000 tokens retained) and still hold the essential guidance.

### Requirement 4: Extend `agent-notes validate` for skills

Add validation rules to `agent_notes/commands/validate.py` with failing-fixture tests for each. Rules are enforced at release pre-flight (via `scripts/release`).

**Errors (block release):**
- `SKILL.md` > 500 lines.
- Estimated tokens in `SKILL.md` (bytes ÷ 3.5) > 5,000.
- `description` frontmatter field > 1,024 chars.
- A reference file > 100 lines without a table of contents at its top (define precisely: a `## Contents` or `## Table of Contents` heading within the first N lines, followed by a list of links/anchors).
- A reference file that links to another reference file, whether in the same skill or another (nesting deeper than one level). Links to external URLs and to anchors within the same file are fine.
- A link from `SKILL.md` to a file that does not exist.
- A frontmatter key outside the allowed set: Claude Code's documented fields (`name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility`) + our own (`group`, `requires_memory`, `triggers`).

**Warnings (do not block):**
- `description` > 250 chars.

**Acceptance:**
- Every new error rule has a failing-fixture test and a passing-fixture test.
- Each test fails on the pre-change code and passes on the fixed code.
- At least one test for the 250-char warning.
- The repo passes validation before release.
- `agent-notes validate` runs in pre-flight and does not block a legitimate release.

### Requirement 5: Never touch Claude Code's synced skills

Install, reinstall cleanup, uninstall (both symlink and copy mode) and `doctor --fix` must never modify, back up, move or delete anything under `~/.claude/skills/synced/` or `~/.claude/skills/.trash/`. Add functional tests that plant files there and assert they are byte-identical afterwards. `agent-notes validate` refuses a skill named `synced`.

**Acceptance:**
- Functional tests in both symlink and copy mode plant test files in `~/.claude/skills/synced/` and `~/.claude/skills/.trash/`.
- After install/reinstall/uninstall/doctor, files are byte-identical.
- A skill directory named `synced` or `.trash` in `agent_notes/data/skills/` fails validation with a clear error.

### Requirement 6: Refresh the rails skill against Fizzy

Restructure the rails skill to match Fizzy's patterns, house style, and stack. This includes splitting the 6 reference files into topic-focused files (~300–400 lines each) and updating content to reflect Fizzy's current practices.

a. **Provenance.** The `SKILL.md` header names Fizzy, pinned to a specific commit SHA and date. It notes that Fizzy tracks Rails main and marks any API that isn't in released Rails. It lists the sources.

b. **Check every pattern.** Verify each one against Fizzy at the pinned commit and its `STYLE.md`/`AGENTS.md`. Keep, fix or remove it. Give each rule a one-line "why" from `STYLE.md`, a reviewed PR or an article. Each reference file ends with a "Sources" list of Fizzy paths and article URLs.

c. **Solid instead of Redis.** Real-time, cache and jobs default to Solid Cable, Solid Cache and Solid Queue, as in Fizzy. Redis is mentioned only as a note for apps already using it.

d. **ViewComponent stays** (owner decision), clearly labelled as not Fizzy/37signals practice and naming its source. Fizzy's default (partials plus helpers) is presented first.

e. **Fill the gaps:** defining `Current` (CurrentAttributes) as Fizzy does; delegated types; multi-tenancy (Fizzy's approach); concerns as a facade over plain objects ("Good concerns"); Turbo 8 morphing and refresh broadcasts; testing conventions from Fizzy's and Writebook's `AGENTS.md`.

f. **Conditional style stays open.** The skill tells the agent to follow the project's RuboCop config (`.rubocop.yml`, e.g. `rubocop-rails-omakase`, which enforces neither style). Fizzy's `STYLE.md` preference (expanded conditionals; guard clauses only at the top of a method) is the 37signals default only when the project has no rule. Apply the same "project config wins" rule to other style points RuboCop can govern.

g. **Licence.** Keep examples short and illustrative, with no verbatim copies of whole Fizzy files, and credit Fizzy/37signals. Spec 001 decision #1 (attribution, generally) stays open.

**Acceptance:**
- A disposition table (each original rails section → kept / updated / removed, plus reason) in the task's output.
- No Redis default in any config example.
- ViewComponent section carries its label and source.
- All gap topics (Current, delegated types, multi-tenancy, concerns, Turbo 8 morphing, testing) present with sections.
- Every reference file ends with a Sources section.
- A RuboCop-defers sentence present in each style guidance.
- Sizes still meet SC-001 and SC-002.

## Success Criteria

- **SC-001:** No docker reference file > ~400 lines (~2.8k tokens estimated) after the split.
- **SC-002:** Every reference file > 100 lines across all skills (including rails and docker after restructuring) has a table of contents (defined: `## Contents` or equivalent heading in the first N lines, followed by a list of links/anchors).
- **SC-003:** All 25 skill descriptions ≤ 250 chars; trigger keywords preserved; first sentence names the primary use case.
- **SC-004:** The five largest `SKILL.md` files (chrome-test, wayfinder, obsidian-memory, diagnosing-bugs, ingest) are ≤ 5,000 tokens; each has a short top section (≤ 500 tokens) with standing rules.
- **SC-005:** `agent-notes validate` passes on the repo; every new error rule has a failing-fixture test and a passing-fixture test; at least one test for the 250-char warning.
- **SC-006:** Symlink and copy mode installs/reinstalls/uninstalls leave `~/.claude/skills/synced/` and `~/.claude/skills/.trash/` byte-identical; skill named `synced` fails validation; skill named `.trash` fails validation.
- **SC-007:** After the split, a copy-mode reinstall over a pre-split install leaves no stale old reference files in `~/.claude/skills/rails|docker` or `~/.agents/skills/rails|docker`, and no backups of our own files. Checked by a functional test using the spec 007a cleanup.
- **SC-008:** Full test suite passes; no regression in existing validation.
- **SC-009:** Rails skill refresh: pinned Fizzy SHA present; zero Redis-default configs; ViewComponent section carries its label; gap topics (Current, delegated types, multi-tenancy, concerns, Turbo 8 morphing, testing) each have a section; every rails reference file ends with Sources; RuboCop-defers sentence present in each style guidance; disposition table in task output.

## Risks

- **Splitting renames reference files:** A copy-mode install from before the split must be cleaned on reinstall (coordinate with spec 007a's ownership cleanup).
- **Token heuristic is approximate:** The bytes ÷ 3.5 estimate is a proxy; final validation should run Claude Code's own measurement if available.
- **Stricter validation can block a release:** Land all content fixes (Requirements 1–3) before the validator gate (Requirement 4) becomes live.
- **Trimming descriptions can lose routing keywords:** Must preserve trigger keywords in every shortened description; verify routing behavior on a few manual prompts.
- **TOC rule must not false-positive:** Some reference files may already have an index by another name (e.g. "Index", "Overview", "Getting Started"). Define the TOC rule precisely before implementation; check existing files against the definition.
- **Fizzy tracks Rails main:** Some APIs taught aren't in released Rails (8.1.4); mark them clearly.
- **Fizzy may contain agent-written code:** Prefer `STYLE.md` and reviewed PRs over a single commit as the source of truth.
- **Rails refresh is the largest task:** This spec includes substantial content review and rewrite; scope and schedule accordingly.
- **O'Saasy licensing on code snippets:** Keep examples short and illustrative, with no verbatim copies of whole Fizzy files; credit Fizzy/37signals.

## Out of Scope

- **Uploadability** (moving custom keys under `metadata:`, an upload-only render). Spec 001 decision #3 remains open.
- **`when_to_use` field in skill frontmatter.** Not in the upload spec and gives no listing-budget gain.
- **Owner-level settings** (`skillListingBudgetFraction`, `skillOverrides`, other Claude Code prefs). Those are the owner's config, not ours.
- **Changes to other CLIs' skill loaders** (Codex, OpenCode).

## Owner's Environment

The owner works with 25 in-house skills plus many installed plugin/superpowers/Anthropic upstream skills on their Claude Code installation. Listing budget is shared.

---

## Tickets

Detailed task breakdown in `tasks.md`. Each task is traceable, test-first, and ends green. Content fixes (T01–T05) and rails refresh (T02) land before the validator gate (T07) ships. Copy-mode reinstall check (T08) depends on T01 and T02 and runs before T09. Synced protection (T09) is independent.

| Ticket | Title | Requirements | Scope |
|---|---|---|---|
| **T01** | Split docker references into topic files (move-only) | Req 1 | Split `docker/compose.md` and `docker/dockerfile.md` into topic-focused files ~300–400 lines each; update `SKILL.md` to router pattern; verify no content lost |
| **T02** | Refresh and split the rails skill against Fizzy | Req 6 + Req 1 | Check every pattern against Fizzy at pinned commit + `STYLE.md`/`AGENTS.md`; split 6 reference files into topic-focused files ~300–400 lines each; fill gaps (Current, delegated types, multi-tenancy, concerns, Turbo 8 morphing, testing); default to Solid (Cable/Cache/Queue) instead of Redis; label ViewComponent; add Sources sections; generate disposition table |
| **T03** | Add table of contents to all reference files > 100 lines | Req 1 | Add `## Contents` section to top of: the split docker files, the split rails files, plus triage/AGENT-BRIEF.md, improve-codebase-architecture/HTML-REPORT.md, prototype/UI.md, triage/OUT-OF-SCOPE.md; define TOC format precisely |
| **T04** | Shorten descriptions for 7 skills (including rails) | Req 2 | Trim descriptions of rsi, code-review, rails, refactoring-protocol, ingest, docker, codebase-design to ≤ 250 chars; preserve trigger keywords; lead with primary use case (run after or with T02 rails refresh) |
| **T05** | Compact the five largest SKILL.md files | Req 3 | Add short standing-rules section to top of chrome-test, wayfinder, obsidian-memory, diagnosing-bugs, ingest; move operator/handoff detail to reference file if needed; keep each ≤ 5,000 tokens |
| **T06** | Manual verification: reference structure and content preservation | Req 1 | Docker: verify before/after that every `##`/`###` heading and code block exists in split output. Rails: verify disposition table against implementation |
| **T07** | Extend `agent-notes validate` for skills | Req 4 | Add error rules for SKILL.md line count, token estimate, description char limit, missing TOC, nesting, missing files, forbidden frontmatter keys; add warning for descriptions > 250 chars; each rule with a failing-fixture test; run pre-flight in `scripts/release` |
| **T08** | Copy-mode reinstall check after split | SC-007 | Functional test: copy-mode install from pre-split state, then reinstall after T01 and T02 complete; verify no stale old reference files in `~/.claude/skills/rails|docker` or `~/.agents/skills/rails|docker`, and no backups of our own files |
| **T09** | Protect synced and trash directories | Req 5 | Add functional tests (test-first): plant files in `~/.claude/skills/synced/` and `.trash/`, run install/reinstall/uninstall/doctor in symlink and copy mode, assert byte-identical; add validation error for skill named `synced` or `.trash`; implement protection only where tests fail |
| **T10** | CHANGELOG and README updates | All | Document the restructuring (docker and rails splits, rails refresh), validation rules, and synced-skill protection; note that spec 007a's cleanup handles renamed reference files |
| **T11** | Full test suite verification | SC-008 + SC-009 | Run the full test suite; confirm all new tests fail on pre-change code and pass on fixed code; no regression in existing validation or install/uninstall behavior |

---

## Verification

To be measured after implementation against the success criteria above.
