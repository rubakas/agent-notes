---
name: brainstorming
description: "Explore multiple approaches before committing — read context, surface tradeoffs, then decide. Use when user wants to compare options, design an API, or says 'brainstorm'."
group: process
---

# Brainstorming

Use when the problem has multiple valid solutions and the choice has long-term consequences: API design, data model, architecture, technology selection.

## Process

### 1. Read the context first

Before generating options, read:
- Existing patterns in the codebase — there may already be an established approach to follow.
- Similar features already implemented — don't invent something the codebase already knows how to do.
- Any stated constraints in tickets, comments, or configuration.

### 2. Generate options (diverge)

Produce at least three meaningfully distinct approaches. For each:
- **Name** — one noun phrase.
- **Summary** — two sentences max.
- **Main advantage** — what it does best.
- **Main cost or risk** — what you're giving up.

Do not evaluate yet. Generate first. If one option is clearly dominant, still generate alternatives — the exercise surfaces the tradeoffs you'd otherwise miss.

If a key technical assumption is unproven, include a **spike option**: a throwaway implementation to test the risky assumption before committing to a direction.

### 3. Apply constraints (filter)

Filter against the project's real constraints:
- Performance requirements
- Team familiarity and maintainability
- Existing patterns and dependencies in the codebase
- Timeline and scope

Remove options that violate hard constraints. Do not remove options just because they're unfamiliar or non-obvious.

### 4. Recommend (converge)

Pick one option. State:
- Which option you recommend.
- Why it wins against the specific alternatives — not in the abstract.
- What you are explicitly trading away — be honest, not diplomatic.

Present the recommendation. Do not begin implementation until the user agrees.

## Anti-patterns

- Generating one real option and two obvious strawmen to make it look like a comparison.
- Recommending the first option you thought of.
- Listing tradeoffs without actually comparing them against each other.
- Skipping the codebase read and inventing patterns from scratch.
- Framing a spike as a commitment — spikes are exploratory, not production code.
