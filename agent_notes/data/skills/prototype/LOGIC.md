# Logic Prototype

A tiny interactive terminal app to drive a state model by hand. Use when the question is about business logic, state transitions, or data shape.

## When this is the right shape

- "Does this state machine handle the edge case where X then Y?"
- "Does this data model let me represent the case where...?"
- "I want to feel out what the API should look like before writing it."

If the question is visual → use [UI.md](UI.md).

## Process

### 1. State the question
Write down the state model and question being prototyped. One paragraph at the top of the file.

### 2. Pick the language
Use the host project's language. Match existing tooling conventions.

### 3. Isolate logic in a portable module
Put logic behind a small, pure interface that could be lifted into the real codebase:
- **Pure reducer** — `(state, action) => state` for discrete events
- **State machine** — explicit states and transitions
- **Pure functions** over a plain data type
- **Class/module** with clear method surface for genuine ongoing state

Keep it pure: no I/O, no terminal code. The TUI imports it; nothing flows back.

### 4. Build the smallest TUI
On every tick, clear screen and re-render:
1. **Current state** — pretty-printed, bold field names, dim less important context
2. **Keyboard shortcuts** — listed at bottom: `[a] add user  [d] delete user  [q] quit`

Loop: initialize → read keystroke → dispatch → re-render → repeat until quit.

### 5. One command to run
Add a script to the project's task runner.

### 6. Capture the answer
When done, record what it taught in NOTES.md, commit message, or ADR. The logic module is worth keeping; the TUI shell gets deleted.

## Anti-patterns
- Don't add tests — a prototype that needs tests is no longer a prototype
- Don't wire to the real database — use in-memory
- Don't generalise — answer one question
- Don't blur logic and TUI — keep the TUI as a thin shell over a pure module
