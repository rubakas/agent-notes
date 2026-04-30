---
name: debugging-protocol
description: "Systematic debugging: build a feedback loop first, then reproduce, hypothesize, and fix. Use when user reports a bug, something is broken, or describes unexpected behavior."
group: process
---

# Debugging Protocol

Never guess. Never change code randomly. Follow the four phases.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a fast, deterministic, pass/fail signal for the bug, you will find the cause. If you don't, no amount of staring at code will save you.

### Ways to build one — try in this order

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) — drives the UI, asserts on DOM/console/network.
5. **Replay a captured trace** — save a real network request or event log; replay through the code path in isolation.
6. **Throwaway harness** — minimal subset of the system that exercises the bug code path with a single function call.
7. **Property / fuzz loop** — if the bug is "sometimes wrong output", run many random inputs and look for the failure.
8. **Bisection harness** — if the bug appeared between two known states (commits, versions), automate "boot at state X, check, repeat" so you can bisect.
9. **Differential loop** — run the same input through old-version vs new-version and diff outputs.

### Iterate on the loop itself

Once you have a loop, ask: Can I make it faster? Can I make the signal sharper (assert on the specific symptom, not "didn't crash")? Can I make it more deterministic (pin time, seed RNG, isolate filesystem)?

A 30-second flaky loop is barely better than no loop. A 2-second deterministic loop is a debugging superpower.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger many times, add stress, narrow timing windows. A 50%-flake bug is debuggable; 1% is not — keep raising the rate.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried. Ask the user for: (a) access to the environment that reproduces it, (b) a captured artifact (log dump, screen recording), or (c) permission to add temporary production instrumentation. Do NOT proceed to Phase 2 without a loop.

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
