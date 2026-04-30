---
name: code-review
description: "Systematic code review: correctness, safety, performance, clarity, consistency. Use when user wants to review code, check quality, or says 'review this'."
group: process
---

# Code Review

Work through these five lenses in order. Report findings grouped by lens, ranked by severity within each group.

## Lens 1 — Correctness

- Does the logic match the stated intent?
- Are edge cases handled: empty input, nil/None, off-by-one, concurrent access, zero/negative values?
- Are error paths handled and surfaced to callers correctly?
- Do the tests cover behavior, not just the happy path?
- Is there new code with no tests at all? That is a blocking issue.

## Lens 2 — Safety

- Is user input validated at the system boundary?
- Are secrets, credentials, or PII handled safely — not logged, not exposed in responses?
- Are SQL queries parameterized, not interpolated?
- Are file paths sanitized before use?
- Does this change affect authentication or authorization logic? If yes, flag for deeper scrutiny.

## Lens 3 — Performance

- Are there N+1 queries — loading a record, then querying for each related record in a loop?
- Are expensive operations (network calls, disk I/O, serialization) inside hot loops?
- Are large collections being loaded into memory when streaming or pagination would suffice?
- Is the change reversible if it causes a production performance regression?

## Lens 4 — Clarity

- Are names accurate — do they describe what, not how?
- Is control flow easy to follow? Guard clauses beat deep nesting.
- Are comments present only where the why is non-obvious? No comments that restate what the code already says.
- Would a new team member understand this without asking?

## Lens 5 — Consistency

- Does this match the existing patterns in the codebase?
- Does it follow project naming conventions?
- Does it introduce a new abstraction or dependency that already exists elsewhere?
- Are the tests written in the same style as existing tests?

## Output format

```
BLOCKING
- [file:line] [finding] — [why it matters]

SUGGESTIONS
- [file:line] [finding] — [alternative if applicable]

APPROVED (if no blocking issues)
```

A BLOCKING finding must be resolved before merge. A SUGGESTION is optional.

## Scope discipline

Do not flag cosmetic changes unless they create real ambiguity. A review that lists 20 nits trains authors to ignore reviews entirely.
