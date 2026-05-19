---
name: to-prd
description: "Turn the current conversation context into a Product Requirements Document. Use when user wants to create a PRD, formalize requirements, or says 'write a PRD'."
group: process
---

# To PRD

Synthesize the current conversation context and codebase understanding into a PRD. Do NOT interview the user — synthesize what you already know.

## Process

1. **Explore the repo** to understand the current state, if you haven't already. Use the project's domain glossary (CONTEXT.md) vocabulary throughout, and respect any ADRs.

2. **Sketch out major modules** you will need to build or modify. Look for opportunities to extract deep modules — ones that encapsulate a lot of functionality behind a simple, testable interface. Check with the user that these match their expectations and which need tests.

3. **Write the PRD** using the template below, then save it to `docs/prd/` (create if needed) with a descriptive filename.

## PRD Template

### Problem Statement
The problem the user is facing, from the user's perspective.

### Solution
The solution, from the user's perspective.

### User Stories
A numbered list of user stories:
1. As an <actor>, I want a <feature>, so that <benefit>

Cover all aspects of the feature extensively.

### Implementation Decisions
- Modules to be built/modified and their interfaces
- Architectural decisions and schema changes
- API contracts and specific interactions

Do NOT include file paths or code snippets — they go stale. Exception: prototype-derived snippets that encode a decision more precisely than prose (state machine, schema, type shape).

### Testing Decisions
- What makes a good test (test external behavior, not implementation)
- Which modules will be tested
- Prior art for similar tests in the codebase

### Out of Scope
What is explicitly not included.

### Further Notes
Any additional context.
