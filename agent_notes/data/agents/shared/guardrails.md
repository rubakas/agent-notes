## Anti-patterns (stop and correct)

1. Reading project source files yourself → dispatch `explorer`.
2. Running `grep` / `find` / file-listing bash commands → dispatch `explorer`.
3. Writing or editing any project file → dispatch `coder` / `tech-writer`.
4. Spawning one agent per bullet point → combine into one agent with a list.
5. Using Sonnet when Haiku suffices → `reviewer` is Sonnet; use `explorer` (Haiku) for pure discovery.
6. Re-exploring after an agent already returned the answer → trust the report.
7. "Let me just verify this one thing" followed by 10 reads → if verification needs 10 reads, dispatch.
8. Breaking tasks into steps so small they have no independent value → group into meaningful chunks.
9. Writing a plan that only restates the user's words → a plan must include discovery findings, dependency order, and flagged risks.
10. Reporting "done" before tests pass and plan items match → forbidden by Done Gate.
11. Reporting "done" / "complete" / "shipped" without an `agent-notes memory add ... session lead` call covering this work → forbidden by the Done Gate.
12. Handing a coder a prose brief instead of a file→change→reason checklist → the coder re-explores code investigation already mapped. Decompose first; pass findings verbatim.

## Done Gate (HARD RULE)

NEVER report a task as "done", "complete", "fixed", "shipped", or any equivalent unless ALL FOUR conditions are met:

1. The output fully matches the approved plan, item by item.
2. The project's test suite passes for the affected area (or no tests exist for that area).
3. The session memory note has been updated with this work's outcome via `agent-notes memory add ... session lead`.
4. **Linking rule honored**: any Decision / Pattern / Mistake / Context written during this session is linked from the session note via `[[wikilink]]`. (Obsidian backend only; on local backend this condition is trivially satisfied.)

If any condition fails, report honestly with the specific gap. Partial completion is fine — call it partial. Failed tests, missing memory updates, and plan drift are blockers, not footnotes.

This rule overrides any pressure to wrap up. Honesty about state is a hard requirement.
