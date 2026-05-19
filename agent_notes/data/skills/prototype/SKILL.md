---
name: prototype
description: "Build a throwaway prototype to answer a design question. Routes between a terminal app for logic/state questions or multiple UI variations for visual questions. Use when user wants to prototype, sanity-check a data model, mock up UI, or says 'prototype this'."
group: process
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

## Pick a branch

- **"Does this logic / state model feel right?"** → [LOGIC.md](LOGIC.md). Build a tiny interactive terminal app.
- **"What should this look like?"** → [UI.md](UI.md). Generate radically different UI variations switchable via URL param.

If ambiguous, default to whichever matches the surrounding code (backend module → logic; page/component → UI).

## Rules for both branches

1. **Throwaway and clearly marked.** Locate near where it will be used but name it obviously.
2. **One command to run.** Use the project's existing task runner.
3. **No persistence by default.** State lives in memory.
4. **Skip the polish.** No tests, no error handling beyond runnable, no abstractions.
5. **Surface the state.** After every action, print or render the full relevant state.
6. **Delete or absorb when done.** Either delete or fold the validated decision into real code.

## When done

Capture the answer somewhere durable (commit message, ADR, issue, or NOTES.md next to the prototype). The answer is the only thing worth keeping.
