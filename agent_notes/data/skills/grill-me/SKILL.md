---
name: grill-me
description: "Interview the user relentlessly about a plan or design until every branch of the decision tree is resolved. Use when user wants to stress-test a plan, get grilled on their design, or says 'grill me'."
group: process
---

# Grill Me

Interview the user relentlessly about every aspect of this plan until you reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

For each question, provide your recommended answer, then wait for a response before continuing.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead of asking.

## When to stop

Stop when:
- Every significant branch of the decision tree has been resolved
- No open questions remain that would change the implementation
- The user signals they have enough clarity to proceed

## Anti-patterns

- Asking multiple questions at once — one at a time only
- Asking vague or obvious questions — each question must resolve a real decision branch
- Accepting a vague answer — press for specifics
- Moving to implementation before all key decisions are resolved
