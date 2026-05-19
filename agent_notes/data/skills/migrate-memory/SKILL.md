---
name: migrate-memory
description: "Run versioned memory vault migrations after an agent-notes upgrade. Use when user says 'migrate memory' or '/migrate-memory', or after installing a new version."
group: process
requires_memory: obsidian
---

# Migrate Memory

Run pending vault migrations after upgrading agent-notes. Migrations are versioned and tracked in `state.json` — each one runs exactly once.

## When to use

- After installing a new version of agent-notes
- When the user says "migrate memory" or `/migrate-memory`
- When `agent-notes memory migrate-memory` reports pending migrations

## Steps

### 1. Check and run pending migrations

```bash
agent-notes memory migrate-memory
```

This lists and runs all pending migrations automatically. If the output is "No pending migrations." — done, nothing to do.

### 2. Optional: enrich auto-derived descriptions

The first migration (`v2.24.0-add-descriptions`) derives note descriptions mechanically from the first line of each note body. These are functional but not ideal for index routing.

If the user wants better descriptions, dispatch `tech-writer` with:

- The vault path (from `agent-notes memory vault`)
- Task: read notes with weak auto-derived descriptions and rewrite them as concise one-liners optimized for index routing (what question does this note answer? what context does it give a future agent?)
- Scope: only rewrite the `description:` frontmatter field — do not touch body content

This step is optional. Skip it unless the user asks for enrichment.

## Constraints

- Obsidian backend only. On local storage, the command exits with a message and no action is taken.
- Migrations are idempotent — running the command twice is safe.
