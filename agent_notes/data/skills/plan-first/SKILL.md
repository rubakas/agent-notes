---
name: plan-first
description: "Plan before coding: decompose, map dependencies, define acceptance criteria"
group: process
---

# Plan First

Before writing any code, produce a written plan the user can review.

## When to apply

Use this skill when the task involves more than one file, has unclear scope,
or when the user hasn't specified an implementation approach.

## Process

1. **Restate the goal** — one sentence. What does "done" look like?
2. **Decompose** — list every discrete subtask needed. Include hidden work
   (tests, migrations, type changes) the user didn't mention.
3. **Map dependencies** — which subtasks must happen before others?
   Mark parallel groups explicitly.
4. **Flag ambiguities** — list anything that needs a decision before work starts.
   Ask one clarifying question if critical information is missing.
5. **Present the plan** — show it to the user before touching any file.
   Wait for approval or correction.

## Output format

```
Plan:
1. [subtask] — [what changes, which files] (parallel group A)
2. [subtask] — [what changes, which files] (parallel group A)
3. [subtask] — [what changes, which files] (after group A)

Questions before starting:
- [ambiguity 1]
```

Do not begin implementation until the user approves the plan.
