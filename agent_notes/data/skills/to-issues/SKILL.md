---
name: to-issues
description: "Break a plan, spec, or PRD into independently-grabbable issues using tracer-bullet vertical slices. Use when user wants to create issues from a plan, break down work, or says 'create issues'."
group: process
argument-hint: "Issue number, URL, or path to the plan/PRD"
---

# To Issues

Break a plan into independently-grabbable issues using vertical slices (tracer bullets).

## Process

### 1. Gather context
Work from the conversation context. If the user passes an issue reference (number, URL, or path), fetch and read it.

### 2. Explore the codebase (if needed)
Use the project's domain glossary (CONTEXT.md) vocabulary. Respect ADRs.

### 3. Draft vertical slices
Each issue is a thin vertical slice cutting through ALL layers end-to-end, NOT a horizontal slice of one layer.

Classify each as:
- **HITL** (human-in-the-loop): requires a decision or review
- **AFK** (away-from-keyboard): can be implemented autonomously

Prefer AFK over HITL.

Rules:
- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones

### 4. Quiz the user
Present the breakdown as a numbered list. For each slice:
- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Blocked by**: which other slices must complete first
- **User stories covered**: which user stories this addresses

Ask: granularity right? Dependencies correct? Merge/split needed? HITL/AFK correct? Iterate until approved.

### 5. Publish issues
For each approved slice, create a GitHub issue (or project issue tracker) with:

```
## Parent
Reference to parent issue (if applicable)

## What to build
End-to-end behavior description (not layer-by-layer).

## Acceptance criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Blocked by
- Blocking ticket reference, or "None - can start immediately"
```

Publish in dependency order (blockers first).
