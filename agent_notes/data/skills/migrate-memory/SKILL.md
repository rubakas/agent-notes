---
name: migrate-memory
description: "Reconcile the Obsidian vault or Wiki knowledge base to the latest canonical format. Use after upgrading agent-notes or when vault structure looks outdated or inconsistent."
group: process
requires_memory: true
---

# Migrate Memory

Reconcile the memory store to the latest format. This skill transforms any state — old layout, missing fields, wrong folder names — into the canonical structure. Works for both Obsidian and Wiki backends.

## When to use

- After upgrading agent-notes
- When the user says "migrate memory" or `/migrate-memory`
- When vault structure looks outdated or inconsistent

## Step 1: Detect backend

```bash
agent-notes memory vault
```

This returns the backend type and vault path. Branch to the appropriate section below.

---

## Obsidian backend

### Reconcile folder structure

The canonical vault layout is:

```
<vault-root>/projects/<project-name>/
├── Patterns/
├── Decisions/
├── Mistakes/
├── Context/
├── Feedback/
├── Sessions/
└── Index.md
```

Reconciliation rules:
- If the project lives under a `notes/` parent and `projects/` does NOT exist → rename `notes/` → `projects/`
- If BOTH `notes/` and `projects/` exist → merge: move all contents from `notes/<project>/` into `projects/<project>/`, skip files that already exist in the destination, then delete the empty `notes/` directory
- At the end: only `projects/` must exist. `notes/` must be gone.
- Create any missing category folders: Patterns, Decisions, Mistakes, Context, Feedback, Sessions
- If `Index.md` is missing, create it with the standard header

### Reconcile note frontmatter

Every `.md` file inside a category folder (NOT Index.md) must have this frontmatter:

```yaml
---
created_at: <ISO 8601 UTC, "Z" suffix>
type: <pattern|decision|mistake|context|session|feedback>
description: "<one-line summary optimized for index routing>"
session: <YYYY-MM-DD_session-id>   # absent on session notes themselves
agent: <agent-name>                 # optional
---
```

Reconciliation rules:
- `created_at` — if missing, derive from filename date prefix (`YYYY-MM-DD_slug.md` → that date at midnight UTC). If no date in filename, use file modification time
- `type` — if missing, derive from parent folder name (lowercase). `Patterns/` → `pattern`, etc.
- `description` — if missing, derive from the first non-heading, non-empty line of the body. Cap at 100 characters, break at word boundary. If no suitable line, use the filename slug with hyphens replaced by spaces
- `session` — leave as-is if present; do not add if absent
- `agent` — leave as-is if present; do not add if absent
- Do NOT remove extra frontmatter fields — only add/fix the required ones

### Reconcile filenames

Canonical filename format: `YYYY-MM-DD_<slug>.md`
- `<slug>` is kebab-case, derived from the note title
- If a file doesn't match this pattern, rename it to match (derive date from `created_at` frontmatter)
- On collision, append `_HHMMSS` before `.md`

### Regenerate Index.md

After all notes are reconciled, regenerate `Index.md`:
- List notes grouped by section in this order: Decisions, Patterns, Context, Mistakes, Feedback
- Within each section, newest first (by `created_at`)
- Each entry: `- [[relative-path|title]] — description`
- Sessions section: last 5 sessions only

---

## Wiki backend

### Reconcile folder structure

The canonical wiki layout is:

```
<vault-root>/knowledge/
├── .obsidianignore
├── raw/                    # immutable source archive
└── wiki/
    ├── index.md
    ├── log.md
    ├── sources/
    ├── concepts/
    ├── entities/
    ├── synthesis/
    └── sessions/
```

Reconciliation rules:
- Create any missing folders: `raw/`, `wiki/`, and all page type folders (`sources/`, `concepts/`, `entities/`, `synthesis/`, `sessions/`)
- If `.obsidianignore` is missing, create it with content: `raw/`
- If `wiki/index.md` is missing, create it with the standard header
- If `wiki/log.md` is missing, create it empty

### Reconcile wiki page frontmatter

Every `.md` file inside `wiki/sources/`, `wiki/concepts/`, `wiki/entities/`, `wiki/synthesis/`, and `wiki/sessions/` must have this frontmatter:

```yaml
---
created_at: <ISO 8601 UTC, "Z" suffix>
updated_at: <ISO 8601 UTC, "Z" suffix>
type: <sources|concepts|entities|synthesis|sessions>
tags: ["tag1", "tag2"]         # optional
aliases: ["alias1"]            # optional
sources: ["raw/source-file.md"] # optional
agent: <agent-name>            # optional
project: <project-name>        # optional
confidence: "<high|medium|low>" # optional
---
```

Reconciliation rules:
- `created_at` — if missing, use file modification time in ISO 8601 UTC
- `updated_at` — if missing, set equal to `created_at`
- `type` — if missing, derive from parent folder name. `concepts/` → `concepts`, etc.
- `tags`, `aliases`, `sources`, `agent`, `project`, `confidence` — leave as-is if present; do not add if absent
- Do NOT remove extra frontmatter fields — only add/fix the required ones

### Reconcile wiki filenames

Canonical filename: `<kebab-case-slug>.md` (no date prefix for wiki pages)
- Slug derived from the H1 heading or title
- Report any non-compliant filenames

### Regenerate wiki/index.md

After all pages are reconciled, regenerate `wiki/index.md`:
- Group by page type in this order: Sources, Concepts, Entities, Synthesis, Sessions
- Each section as a markdown table: `| Page | Tags | Updated |`
- Each row: `| [[slug]] — description | #tag1 #tag2 | YYYY-MM-DD |`
- Description: first sentence of body content, capped at 80 characters

---

## Report

Print a summary of changes made:
- Backend: obsidian or wiki
- Folders: created / renamed / merged / removed
- Notes with updated frontmatter (count)
- Notes already compliant (count)
- Filenames: all OK or list non-compliant
- Index regenerated: yes/no

## Constraints

- Never delete individual notes. Only add/fix metadata, rename, and merge folders.
- Preserve note body content exactly — only touch frontmatter and filenames.
- When merging folders, skip files that already exist at the destination (do not overwrite).
