---
name: debugging-protocol
description: "4-phase systematic debugging: instrument → evidence → hypothesis → fix"
group: process
---

# Debugging Protocol

Never guess. Never change code randomly. Follow the four phases.

## Phase 1 — Instrument

Before forming any hypothesis, add observability:
- Add logging at the entry and exit of the failing code path.
- Log inputs, intermediate values, and outputs — not just that something happened.
- If a test is failing: read the **full stack trace** before doing anything else.
- If a runtime error: reproduce in the smallest possible isolated case.

Do not modify production logic in this phase.

**For regressions:** run `git log --oneline -20` and use `git bisect` to find the commit that introduced the failure before instrumenting. Knowing when it broke tells you where to look.

## Phase 2 — Gather evidence

Run the instrumented version. Collect:
- Exact error message and file:line location.
- What values are actually present vs. what was expected.
- The full call stack at the point of failure.
- Whether this is a **code bug** or a **test bug** — read the test's intent before assuming the production code is wrong.

Check dependency changelogs if a third-party library was recently updated and the failure is at an integration boundary.

## Phase 3 — Form a hypothesis

State it explicitly before touching anything:

> "I believe the bug is caused by X, because the evidence shows Y."

Test with the smallest possible change — one that confirms or disproves the hypothesis without being the permanent fix. If the hypothesis is wrong: return to Phase 2 with the new evidence. Do not stack changes.

## Phase 4 — Fix

Apply the minimal fix for the root cause:
- Fix the root cause, not the symptom.
- Remove all instrumentation from Phase 1.
- Run the full test suite.
- Confirm the original failure is gone and nothing else regressed.

## Escalation rule

Three failed hypothesis cycles means stop and do an architectural review. The bug likely signals that a design assumption is wrong, not just a logic error in one function.
