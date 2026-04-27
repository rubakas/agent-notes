---
name: plan-first
description: "Plan before coding: read first, decompose, map dependencies, flag risks"
group: process
---

# Plan First

Before writing any code, produce a written plan the user can review.

## When to apply

Any task touching more than one file, with unclear scope, or where multiple approaches exist. For trivial single-file changes you already understand fully — skip the plan, just do it.

## Process

### 1. Read first

Before planning, read the relevant existing code. Look for:
- Existing patterns you should follow
- Similar features already implemented — don't reinvent
- Constraints that rule out certain approaches

### 2. Restate the goal

One sentence. What does "done" look like from the user's perspective?

### 3. Decompose

List every discrete subtask. Include hidden work the user didn't mention:
- Tests
- Migrations or schema changes
- Type definitions
- Config or environment changes
- Cleanup of code being replaced

### 4. Map dependencies

Which subtasks must happen before others? Mark parallel groups explicitly. Flag tasks that require a user decision before you can proceed.

### 5. Flag risks

List anything that could block the plan:
- Missing information or ambiguities
- Assumptions that need verification
- Changes that could break existing behavior

### 6. Present and wait

Show the plan. Do not touch any file until the user approves or corrects it. If the scope is too large, propose splitting into phases.

## Output format

```
Plan:
1. [subtask] — [files affected] (parallel group A)
2. [subtask] — [files affected] (parallel group A)
3. [subtask] — [files affected] (after group A)

Risks / questions:
- [item needing decision or verification]
```

## Anti-patterns

- Planning without reading the codebase first
- Breaking tasks into steps so small they have no independent value
- Starting implementation before the plan is approved
- Writing a plan that only restates what the user said
