---
name: debugging-protocol
description: "4-phase systematic debugging: instrument → evidence → hypothesis → fix"
group: process
---

# Debugging Protocol

Never guess. Never change code randomly. Follow the four phases.

## Phase 1 — Instrument

Add observability before forming any hypothesis:
- Add logging at the entry and exit of the failing code path.
- Log the inputs, intermediate values, and outputs.
- If a test is failing: read the full stack trace and error message before anything else.
- If a runtime error: reproduce it in isolation (smallest possible case).

Do not touch production logic in this phase.

## Phase 2 — Gather evidence

Run the instrumented version. Collect:
- Exact error message and location.
- What values are actually present vs. what was expected.
- The call stack at the point of failure.
- Any recent changes that correlate with when the bug appeared (`git log --oneline -20`).

## Phase 3 — Form a hypothesis

State the hypothesis explicitly:
> "I believe the bug is caused by X, because the evidence shows Y."

Test the hypothesis with the smallest possible change — ideally one that makes the bug
disappear in a controlled way (not a permanent fix yet). If the hypothesis is wrong,
return to Phase 2 with the new evidence.

## Phase 4 — Fix

Apply the minimal fix that addresses the root cause:
- Fix the root cause, not the symptom.
- Remove all instrumentation added in Phase 1.
- Run the full test suite.
- Confirm the original failure no longer reproduces.

## Escalation rule

If three hypothesis-fix cycles fail: stop and do an architectural review.
The bug likely indicates a deeper design assumption is wrong.
