---
name: refactoring-protocol
description: "Safe refactoring: green tests first, one extraction at a time, structure OR behavior never both. Use when user wants to refactor code, reduce duplication, or says 'clean this up'."
group: process
---

# Refactoring Protocol

Refactoring means improving the structure of code without changing its behavior. The moment you change behavior, you are no longer refactoring — you are adding a feature or fixing a bug. These are different activities and must not be mixed.

## Prerequisites — before you start

1. **Tests must be green.** If the code has no tests, write characterization tests first that document what it currently does (not what it should do). Do not refactor untested code.
2. **Understand what you're changing.** Read the code and identify exactly which smell you're addressing.
3. **One session, one concern.** Name the refactor before starting: "extract payment logic into a service", "rename variables to match domain language", "remove duplication in validation". If you find yourself listing more than one, finish one, commit, then start the next.

## Code smells worth addressing

- **Long method** — does more than one thing; split by responsibility.
- **Duplicated logic** — same decision made in multiple places; extract to one location.
- **Misleading names** — name describes something other than what the code does.
- **Deep nesting** — more than two levels of if/for; extract guard clauses or methods.
- **Large class** — handles multiple concerns; split by cohesion.
- **Primitive obsession** — using raw strings or ints for domain concepts; introduce a value object.
- **Feature envy** — a method that uses more of another class than its own; move it.

## Process

### Step 1 — Run tests (confirm green)

If any test is failing before you start: stop. Do not refactor broken code.

### Step 2 — Make one extraction

Extract one method, rename one variable, move one class. Not all at once.

### Step 3 — Run tests immediately

Every extraction gets a test run. If tests go red:
- Undo the extraction. Do not try to fix it forward.
- Understand why it broke before attempting again.

### Step 4 — Commit

Each logical extraction is its own commit. This makes it reversible and reviewable independently.

### Step 5 — Repeat

Return to Step 2 for the next extraction.

## Hard rules

- **Structure OR behavior in one commit, never both.** If you find a bug while refactoring: stash the refactor, fix the bug in a separate commit, then resume. Mixing them makes the change impossible to review and risky to revert.
- **Do not optimize during refactor.** Performance tuning is a separate session with its own measurement baseline.
- **Do not add features during refactor.** If you notice a missing edge case: note it, address it in a separate commit after the refactor is complete.
- **Stop when the smell is gone.** Over-refactoring is as harmful as under-refactoring.

## Done means

- Tests still green.
- One code smell addressed.
- Each logical change committed separately.
- No behavior was changed.
- No new features or bug fixes were mixed in.
