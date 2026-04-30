---
name: setup-project-context
description: "Bootstrap a CONTEXT.md domain glossary in the current project. Use when starting a new project, when the AI is using inconsistent terminology, or when user says 'set up context' or 'create a glossary'."
group: process
---

# Setup Project Context

Create a `CONTEXT.md` at the project root — a living domain glossary that gives you and the AI a shared language.

## Why it matters

When you and the AI use the same precise terms, every session benefits: variable and function names stay consistent, the AI spends fewer tokens decoding jargon, and code reviews stop re-litigating terminology.

## Process

1. **Explore** the codebase briefly — read README, main entry points, key domain types. Note any terms that appear frequently or are used inconsistently.

2. **Interview the user** about the key domain concepts. Ask: "What are the 3-5 most important things in this system?" and "Are there terms the team argues about or uses differently?"

3. **Draft `CONTEXT.md`** at the project root using this format:

```md
# {Context Name}

{One or two sentences describing what this context is.}

## Language

**{Term}**:
{One sentence: what it IS, not what it does.}
_Avoid_: {synonyms to stop using}

## Relationships

- A **{Term}** contains one or more **{OtherTerm}**

## Example dialogue

> **Dev:** "{sentence using the terms naturally}"
> **Domain expert:** "{response that demonstrates boundaries between concepts}"

## Flagged ambiguities

- "{word}" was used to mean both **X** and **Y** — resolved: {resolution}.
```

4. **Rules to follow when writing:**
   - Be opinionated — pick the best word and list others as aliases to avoid
   - One sentence per definition — what it IS, not what it does
   - Only include terms specific to this project — not general programming concepts
   - Flag conflicts explicitly under "Flagged ambiguities"
   - Write an example dialogue showing how terms interact naturally

5. **Show the user the draft** before saving. Iterate once if needed.

## Multi-context repos (monorepos)

If the repo has distinct bounded contexts (e.g., ordering, billing, fulfillment), create:
- Individual `CONTEXT.md` inside each context's directory
- A `CONTEXT-MAP.md` at the root listing contexts, where they live, and how they relate

## Done means

- `CONTEXT.md` exists at the project root (or context-specific location)
- Every key domain term has a one-sentence definition and listed synonyms to avoid
- User has reviewed and approved the glossary
