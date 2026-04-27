---
name: code-review
description: "Systematic code review: correctness, safety, clarity, consistency"
group: process
---

# Code Review

When reviewing code, work through these four lenses in order. Report findings
grouped by lens, ranked by severity (blocking → suggestion).

## Lens 1 — Correctness

- Does the logic match the stated intent?
- Are edge cases handled (empty input, nil/None, off-by-one, concurrent access)?
- Are error paths handled and surfaced correctly?
- Do the tests cover the behavior, not just the happy path?

## Lens 2 — Safety

- Is user input validated at the system boundary?
- Are secrets, credentials, or PII handled safely (no logging, no exposure)?
- Are SQL queries parameterized?
- Are file paths sanitized before use?
- Does the change affect authentication or authorization logic?

## Lens 3 — Clarity

- Are names accurate? Does the name describe what the thing does, not how?
- Is control flow easy to follow? (Guard clauses over deep nesting.)
- Are comments present only where the "why" is non-obvious?
- Would a new team member understand this without asking?

## Lens 4 — Consistency

- Does this match the patterns already in the codebase?
- Does it follow project naming conventions (checked against existing files)?
- Does it introduce new abstractions or dependencies that already exist elsewhere?

## Output format

```
BLOCKING
- [file:line] [finding] — [why it matters]

SUGGESTIONS
- [file:line] [finding] — [optional: alternative]

APPROVED (if no blocking issues)
```

A BLOCKING finding must be resolved before merge. A SUGGESTION is optional.
