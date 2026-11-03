# Upstream drift: vendored skills compared with mattpocock/skills (2026-10-30, general-purpose agent)

## Where we stand

- **Manifest:** THIRD_PARTY_SKILLS.yaml lists 16 skills, all from mattpocock/skills.
  - The sync commit is 391a270 (2026-07-10), imported in our commit 7af8103.
  - There is no sync tooling. The manifest header (HEAD c55ee46, 46 commits) is stale.
- **Upstream HEAD:** a496f55 (2026-10-29) is 261 commits ahead of our sync. 63 of those touch vendored paths.
- **Status:** all 16 skills changed upstream. None were removed or renamed. Our local edits match the manifest.
- **Upstream clone (read-only):** scratchpad/upstream/

## Changes across all skills

- **3216582:** removes em-dashes. Cosmetic.
- **d80fa0f (+ ed0de59):** renames `CONTEXT.md`/`CONTEXT-MAP.md` to `GLOSSARY.md`/`GLOSSARY-MAP.md` and offers a `git mv`.
  - It's all-or-nothing for us. It touches 6 skills, `tests/skill_evals/prompts.yaml` and the README.
  - **OWNER DECISION.**
- **d28dfdc / fcf0071 / 447ca70:** "Call the Skill tool with 'X'" wording.
- **1dab982:** skills no longer call user-invoked skills. We already did this in spec 009 Req 8.
- **14bfbbd / 7739eae:** harness-neutral sub-agent wording ("fresh context window").
- **Upstream invocation.md:** descriptions of user-only skills drop "Use when". We keep ours, per spec 009.

## Per skill

| Skill | Recommendation | What to take, keep or avoid |
|---|---|---|
| grill-me | keep (frozen) | |
| grill-with-docs | keep (frozen) | |
| grilling | keep (frozen) | Upstream is a full rewrite into rounds over a frontier of questions, with ❓/➡️ formatting and fact-finding sub-agents. |
| diagnosing-bugs | PARTIAL | Take f3fc563: when the red was forced by a mutation, diff against a pristine copy. Take efce423/bda79a3: a Redact section, framed with "never read credential files". Keep our post-mortem suggestion. |
| improve-codebase-architecture | PARTIAL | Take 45afd80: a scoping step (the user's direction, else hot spots from `git log`). Keep our explorer and our HTML-REPORT. Upstream's version loads an unpinned CDN with mermaid "loose". |
| codebase-design | keep | |
| domain-modeling | keep | Unless GLOSSARY is adopted. Upstream's trigger phrasing is worth folding into our description. |
| prototype | keep | Upstream's LOGIC.md became an HTML-only design change. |
| handoff | keep | Ours is stricter. |
| research | keep | |
| to-spec | keep | Optionally drop the "PRD" wording. |
| to-tickets | PARTIAL | Take cffab50/9e2abf8: tickets become sub-issues of the source issue, and the "Blocked by" section is omitted when blocking is native. Keep our ready-for-agent exception. |
| triage | keep, never pull wholesale | Upstream still has the AI disclaimer and an ungated PR checkout-and-run. |
| wayfinder | PARTIAL | Take 8295b8e: only `wayfinder:` labels, real ids (not `#<n>` placeholders), resolve by label type. Optionally take the "decision tickets" naming. Do NOT take 2602257: its research fan-out pushes branches and breaks one-ticket-per-session and the allowlist. |
| code-review | PARTIAL | Take 3da8c01: find every standards file, with CODING_STANDARDS.md and CONTRIBUTING.md mandatory, and run both sub-agents in the foreground, then aggregate. |
| setup-agent-tracker | PARTIAL | See below. Never pull upstream's `--body "..."` lines or its ungated label creation. |

**setup-agent-tracker** (upstream name: setup-matt-pocock-skills) takes these changes:

- **a.** 5b7cade: GitHub "Read an issue" uses `gh issue view <n> --json number,title,body,labels,comments`. This is a BUG FIX.
- **b.** ed0de59: native blocking via `gh issue create --blocked-by` and `edit --add-blocked-by` (gh 2.94+, with a REST fallback), a "Count open blockers" command, and the sub-issue operation (`--parent`, `--add-sub-issue`).
- **c.** 59db609: before filing in a fork, check `gh repo view --json nameWithOwner`, so issues go to the user's own repo.
- **d.** GitLab `-O json` in place of `-F json`, and the links-API frontier. Not verified; glab isn't installed.
- **e.** Reachable-repo wiring (`git init`, `remote add`), but only with a confirmation.

## Bugs in our current files

1. **issue-tracker-github.md**, "Read an issue" / "fetch the relevant ticket". Checked with gh 2.102.0:
   - `gh issue view N --comments --jq …` fails: "cannot use `--jq` without specifying `--json`".
   - Piped output of `--comments` alone prints only the comments.
2. **code-review**: the Spec axis goes to `analyst`, which has no Bash (same as finding C1 in skills-review).
3. **issue-tracker-gitlab.md**, lines 12, 13, 36 and 56 use `-F json`. Upstream issue #1143 says this prints a table. Unverified.

## Security scan of upstream HEAD

- Clean: no hidden Unicode, no `!` preprocessing, frontmatter limited to name/description/argument-hint/disable-model-invocation, no hooks or allowed-tools, no injection text.
- Side effects to gate if any of these are ever pulled:
  - wayfinder's branch push;
  - setup's `git init`/`remote add` and label creation;
  - triage's PR run;
  - grilling's sub-agents;
  - prototype's shareable demo.

## Upstream skills not imported

- **implement-spec** (new): parallel worktree implementers, then merge, then a draft PR. Spec 009 4c decided no implement skill.
- **implement**: single-session implementation.
- **pr**: a PR template; overlaps our git skill.
- **retro**: a session retrospective that reads local session logs (a privacy consideration).
- **wizard**: a bash wizard for human-only steps such as credentials; needs a review against our credentials rule.
- **git-guardrails-claude-code**: installs a `settings.json` hook; overlaps agent-notes' own guards.
- **Previously dropped:** tdd and writing-for-agents (we dropped them in 8abfeeb as duplicates).
- **Unstable:** chief-of-staff, claude-handoff, setup-ts-deep-modules.
- **Removed upstream:** resolving-merge-conflicts.
