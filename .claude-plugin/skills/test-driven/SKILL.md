---
name: test-driven
description: "RED-GREEN-REFACTOR: write failing test first, then implement, then clean up"
group: process
---

# Test-Driven Development

## The three rules

1. Write a failing test before writing any production code.
2. Write the minimum production code to make the test pass.
3. Refactor only when tests are green.

## Process

### RED — write a failing test
- Identify the smallest behavior to verify.
- Write the test. Run it. Confirm it fails for the right reason (not a syntax error,
  not a wrong import — the actual assertion must fail).
- Do not write production code yet.

### GREEN — make it pass
- Write the minimum code to pass the test. No extras.
- Run the test. Confirm it passes.
- If it still fails: diagnose the test failure before writing more code.

### REFACTOR — clean up
- Eliminate duplication.
- Improve naming.
- Extract helpers if clarity improves.
- Tests must stay green throughout refactor.

## When NOT to apply

- Exploratory spikes where you're learning the API.
- Tests that require extensive mocking that obscures the behavior being tested —
  in those cases, write an integration test first instead.

## Acceptance gate

A feature is not done until:
- All new tests pass.
- No existing tests regressed.
- No dead code or commented-out experiments remain.
