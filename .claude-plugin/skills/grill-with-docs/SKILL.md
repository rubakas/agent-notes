---
name: grill-with-docs
description: "Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates CONTEXT.md inline as decisions crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions."
group: process
---

# Grill With Docs

Like `/grill-me`, but domain-aware. Interview the user about their plan while cross-referencing the project's domain glossary and architecture decisions. Update documentation inline as terms and decisions crystallise.

## Setup

Before interviewing, explore the project for existing documentation:

```
/
├── CONTEXT.md              ← single-context glossary
├── CONTEXT-MAP.md          ← multi-context map (if present)
└── docs/
    └── adr/
        ├── 0001-*.md       ← architecture decision records
        └── 0002-*.md
```

If `CONTEXT-MAP.md` exists, infer which context the current topic relates to. If no `CONTEXT.md` exists, create it lazily when the first term is resolved (run `/setup-project-context` pattern).

## During the session

### Interview one question at a time

Walk down each branch of the design tree, resolving dependencies between decisions one by one. For each question, provide your recommended answer, then wait before continuing.

If a question can be answered by exploring the codebase, explore instead of asking.

### Challenge against the glossary

When the user uses a term that conflicts with `CONTEXT.md`, call it out immediately:
> "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term:
> "You're saying 'account' — do you mean the Customer or the User? Those are different things in your glossary."

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch — capture as they happen. Format:

```md
**{Term}**:
{One sentence definition — what it IS.}
_Avoid_: {synonyms to stop using}
```

Only include terms specific to this project's domain, not general programming concepts.

### Offer ADRs sparingly

Only offer to create an ADR when ALL THREE are true:
1. **Hard to reverse** — cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — genuine alternatives existed and you picked one for specific reasons

ADR format — file as `docs/adr/NNNN-slug.md` (increment from highest existing number):

```md
# {Short title of the decision}

{1-3 sentences: context, decision, and why.}
```

That's it. The value is recording *that* a decision was made and *why*.

### Cross-reference with code

When the user states how something works, check whether the code agrees. Surface contradictions:
> "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

## Done means

- All significant decision branches resolved
- `CONTEXT.md` updated with any new or clarified terms
- ADRs created for decisions that meet the three-gate criteria
- No implementation started until user signals clarity
