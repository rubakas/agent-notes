# Skills review, 2026-10-30 (reviewer agent, read-only)

Scope: every skill except rails, at HEAD f20fff2. No spec 009 regressions found. The validator reports 0 errors and the 3 accepted "Use when" warnings.

## Verdicts

- **OK:**
  - codebase-design
  - docker
  - domain-modeling
  - git
  - the grill trio
  - improve-codebase-architecture
  - prototype
  - research
  - setup-agent-tracker
  - to-spec
  - triage
  - wayfinder
- **Minor:**
  - chrome-test
  - diagnosing-bugs
  - handoff
  - ingest
  - obsidian-memory
  - refactoring-protocol (it also has one medium finding)
  - to-tickets
- **Needs work:**
  - code-review
  - migrate-memory
  - rsi

## Findings

### High

**M1 — migrate-memory/SKILL.md:35, 46-48**
- **Problem:** the skill describes a `<vault>/projects/<project>/` layout and tells the model to rename `notes/` to `projects/` and merge. The code writes a flat `<vault>/<Category>/`, or `<vault>/<cwd>/<Category>/` per project (`obsidian_backend.py:217-235`).
- **Risk:** a model-invoked run would restructure the vault.
- **Fix:** add `disable-model-invocation: true`, then rewrite the skill to the real layout or reduce it to `agent-notes memory index`.

### Medium

**M2 — migrate-memory:81-87, 98**
- **Problem:** the model regenerates Index.md by hand and writes vault files directly. `obsidian-memory:14` says never to write vault files directly.
- **Fix:** use `agent-notes memory index` instead.

**C1 — code-review/SKILL.md:64, 73**
- **Problem:** the Spec axis goes to `analyst`. That agent has `Read, Grep, Glob, WebFetch`, `disallowedTools: Write, Edit, Bash`, so it cannot run `git diff`.
- **Fix:** capture the diff to a temp file and pass its path, or use `reviewer` for both axes.

**R1 — rsi:21-34**
- **Problem:** each pass can start up to 5 scanners, plus a coder and a reviewer per change, for up to 5 passes. Nothing says to work inline when the scope is small. The Opus 5 guidance is to keep spawn counts low and not use subagents to verify.
- **Owner decision:** the per-change reviewer is the anti-gaming gate.

**R2 — rsi:42**
- **Problem:** step 2 points scanners at "the smells in the code-review skill's smell baseline". Subagents don't inherit the skills the main session invoked, and no agent preloads them with `skills:`.
- **Fix:** paste the baseline into the briefs.

**F1 — refactoring-protocol:19**
- **Problem:** the same unreachable smell-baseline reference as R2.
- **Fix:** point to `code-review` step 3, or move the list into a `user-invocable: false` reference skill.

### Low

**O1 — obsidian-memory:129, 152; ingest:142, 205**
- **Problem:** `memory show` reads only the flat layout (`notes.py:104`), yet the docs say reads search both layouts.

**O2 — obsidian-memory:207**
- **Problem:** "MUST read" is emphatic wording.
- **Fix:** plain wording.

**O3 — obsidian-memory:177**
- **Problem:** it cites `global-claude.md`, the template, where it should cite the global CLAUDE.md.

**I1 — ingest:196**
- **Problem:** "Be thorough" is anti-laziness prompting.
- **Fix:** delete it.

**CT1 — chrome-test:36, 97**
- **Problem:** it says "the lead". Under Claude Code the lead is the main session.

**CT2 — chrome-test SKILL.md**
- **Problem:** 17,441 bytes is about 4,983 tokens against the 5,000 limit.
- **Fix:** move lines 140-217 (the request template) into `REQUEST-TEMPLATE.md`.

**D1 — diagnosing-bugs:31**
- **Problem:** "Be aggressive. Be creative. Refuse to give up."
- **Fix:** delete it.

**D2 / X1 — missing `argument-hint`**
- diagnosing-bugs: `[symptom or failing test]`
- refactoring-protocol: `[file or smell]`
- prototype: `[question]`
- improve-codebase-architecture: `[area, optional]`

**R3 — rsi:14, 20, 31, 58**
- **Problem:** NEVER, Do NOT and ONE in caps.
- **Fix:** lowercase them.

**R4 — rsi:26**
- **Problem:** "test-writer (read-only pass)", but test-writer can write.
- **Fix:** use reviewer or system-auditor, or say "write nothing".

**R5 — rsi description**
- **Problem:** "wants hardening" is too broad for a model-invocable skill that commits.

**H1 — handoff**
- **Problem:** "Suggested skills" may name user-only skills.
- **Fix:** list model-invocable ones as skills, and user-only ones as `/name` for the user to run.

**T1 — to-tickets:70**
- **Problem:** native blocking is mentioned without a pointer to the tracker doc's Blocking entry.

### Notes

- **X2:** codebase-design and domain-modeling could take `user-invocable: false`. Optional.
- **X3:** `when_to_use` brings no gain. It shares the 1,536-character cap with the description.
- **X4:** `group` and `requires_memory` are used by the code (`skill_registry.py:92,96`, `doctor.py:74-80`, `memory/install.py:115-124`). `stability` is read at `skill_registry.py:99` but not allowed by the validator; this is a known spec 009 follow-up.

## Durable facts

- Subagents don't inherit invoked skills, and no agent preloads any. A skill that refers to another skill's content must paste that content into its sub-agent briefs.
- `analyst` has no Bash.
