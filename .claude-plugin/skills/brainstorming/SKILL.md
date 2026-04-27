---
name: brainstorming
description: "Explore multiple approaches before committing — surface tradeoffs, then decide"
group: process
---

# Brainstorming

Use this skill when the problem has multiple valid solutions and the choice has
long-term consequences (API design, data model, architecture decision).

## Process

### 1. Generate options (diverge)

Produce at least three distinct approaches. For each:
- Name it (one noun phrase).
- Describe it in two sentences max.
- List the main advantage.
- List the main risk or cost.

Do not evaluate yet. Generate first.

### 2. Apply constraints (filter)

Filter options against the project's real constraints:
- Performance requirements
- Team familiarity
- Existing patterns in the codebase
- Timeline / scope

Eliminate options that violate hard constraints. Do not eliminate options just because
they're unfamiliar.

### 3. Recommend (converge)

Pick one option. State:
- Which option you recommend.
- Why it wins over the alternatives.
- What you're trading away (be honest about the downside).

Present the recommendation to the user. Do not begin implementation until they agree.

## Anti-patterns to avoid

- Generating only one option dressed up as brainstorming.
- Recommending the first option you thought of.
- Listing tradeoffs without actually comparing them.
