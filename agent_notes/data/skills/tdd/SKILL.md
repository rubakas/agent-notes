---
name: tdd
description: "RED-GREEN-REFACTOR via vertical slices: one failing test, one implementation, repeat. Use when user wants TDD, test-first development, or says 'red-green-refactor'."
group: process
---

# Test-Driven Development

## The contract

1. No production code before a failing test.
2. The minimum code to pass the test — nothing more.
3. Refactor only while tests are green.

## Anti-pattern: Horizontal slicing

**Do not write all tests first, then all implementation.** This is horizontal slicing — treating RED as "write all tests" and GREEN as "write all code."

This produces bad tests: written in bulk against imagined behavior, testing the shape of things (data structures, function signatures) rather than user-facing behavior. Tests become insensitive to real changes.

**Correct approach: vertical slices via tracer bullets.** One test → one implementation → repeat. Each test responds to what you learned from the previous cycle.

```
WRONG: RED: test1, test2, test3, test4 → GREEN: impl1, impl2, impl3, impl4
RIGHT: RED→GREEN: test1→impl1, RED→GREEN: test2→impl2, RED→GREEN: test3→impl3
```

Because you just wrote the code, you know exactly what behavior matters and how to verify it.

## RED — write a failing test

- Identify the smallest behavior to verify.
- Name the test as a specification: `test_returns_empty_list_when_no_results`, not `test_search`.
- Run it. Confirm it fails for the **right reason** — the assertion fails, not a syntax error or import problem.
- Do not write production code yet.

## GREEN — make it pass

- Write the minimum code to pass the test. Hardcode values if that's all it takes — you'll triangulate with the next test.
- Run the test. Confirm green.
- If still failing: read the failure output carefully before changing anything else.

## REFACTOR — clean up

- Eliminate duplication.
- Improve names.
- Extract where it improves clarity, not just to reduce line count.
- Run tests after every change. If they go red: undo the refactor, don't push through.

## Test scope rules

- Test **behavior** from the outside, not implementation details.
- Do not test private methods directly — test through the public interface.
- Prefer fewer, meaningful assertions over many trivial ones.
- If a test requires more than three mocks to set up: it is testing too much. Split the unit.

## When NOT to apply

- Exploratory spikes where you're learning an unfamiliar API — spike first, then write tests for what you keep.
- Tests that require so much mocking the mock becomes the thing being tested — write an integration test instead.
- Throwaway scripts with no expected lifetime.

## Flaky tests

If a new test passes sometimes and fails other times: stop and fix it before continuing. A flaky test is worse than no test — it trains you to ignore failures.

## Done means

- All new tests pass.
- No existing tests regressed.
- Test names describe the behavior they verify.
- No dead code or commented-out experiments remain.
