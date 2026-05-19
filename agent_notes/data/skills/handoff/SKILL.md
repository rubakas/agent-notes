---
name: handoff
description: "Compact the current conversation into a handoff document for another agent to pick up. Use when the session is getting long, context is degrading, or you need to transfer work to a fresh session."
group: process
argument-hint: "What will the next session be used for?"
---

# Handoff

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save it to a path produced by `mktemp -t handoff-XXXXXX.md` (read the file before you write to it).

## What to include

1. **Goal**: What the user is trying to accomplish (1-2 sentences)
2. **Current state**: What has been done so far, what works, what doesn't
3. **Next steps**: What the next session should focus on
4. **Key decisions**: Decisions made during this session that the next agent needs to know
5. **Relevant files**: Paths to files that were modified or are relevant
6. **Skills to use**: Suggest which skills the next session should invoke

## Rules

- Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.
- Keep it concise — the handoff should fit in a single context window read.
- If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
- If using the obsidian memory backend, also save a session note via `agent-notes memory add` before creating the handoff.
