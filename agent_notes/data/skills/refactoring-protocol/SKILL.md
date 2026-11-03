---
name: refactoring-protocol
description: "Guides safe refactoring: green tests first, one extraction at a time, no behavior changes. Use when refactoring code, reducing duplication, or the user says 'clean this up'. For an iterative multi-pass loop use rsi."
group: process
argument-hint: "[file or smell]"
---

# Refactoring Protocol

Refactoring changes structure only; mixing in behavior changes is a different activity.

Do it inline for a small refactor. When delegating to `refactorer`, paste this protocol and the chosen smell into the brief.

## Prerequisites — before you start

1. **Tests must be green.** If the code has no tests, write characterization tests first that document what it currently does (not what it should do). Do not refactor untested code.
2. **Understand what you're changing.** Read the code and identify exactly which smell you're addressing.
3. **One session, one concern.** Name the refactor before starting: "extract payment logic into a service", "rename variables to match domain language", "remove duplication in validation". If you find yourself listing more than one, finish one, commit, then start the next. If the change needs a module or interface redesign, stop and suggest the user run `/improve-codebase-architecture`.

## Code smells worth addressing

Work from the smell baseline in `code-review/SMELLS.md` (sibling skill directory); pick one smell from it and address only that. Sub-agents don't inherit skills, so paste its content into any sub-agent brief.

## Process

Ask the user once, before the first change: "Commit each step as I go?" Yes → commit each step locally; No → leave the changes uncommitted and list them in the report. Never push.

### Step 1 — Run tests (confirm green)

If any test is failing before you start: stop. Do not refactor broken code.

### Step 2 — Make one extraction

Extract one method, rename one variable, move one class. Not all at once.

### Step 3 — Run tests immediately

Every extraction gets a test run. If tests go red:
- Undo it (`git checkout -- <files>` if uncommitted, `git revert` if committed). Do not try to fix it forward.
- Understand why it broke before attempting again.

### Step 4 — Commit

Commit per the answer given in Process: each logical extraction is its own commit, so it is reversible and reviewable independently.

### Step 5 — Repeat

Return to Step 2 for the next extraction.

## Hard rules

- **Structure OR behavior in one commit, never both.** If you find a bug while refactoring: set aside the refactor changes (save them as a patch with `git diff > file`, or stash them), fix the bug in a separate commit, then resume. Mixing them makes the change impossible to review and risky to revert.
- **Never achieve green by weakening the tests.** Do not weaken, skip, delete, or rewrite a test to make it pass after a refactor. If a test breaks, the refactor changed behavior by definition — fix or revert the refactor, not the test. The test suite is the invariant the refactor must preserve.
- **Do not optimize during refactor.** Performance tuning is a separate session with its own measurement baseline.
- **Do not add features during refactor.** If you notice a missing edge case: note it, address it in a separate commit after the refactor is complete.
- **Stop when the smell is gone.** Over-refactoring is as harmful as under-refactoring.

## Done means

- Tests still green.
- One code smell addressed.
