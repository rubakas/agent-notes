---
name: ingest
description: "Ingest the current project or external sources (URLs, files, folders) into the knowledge base. Creates category-mapped notes with session linking in the Obsidian backend. Use when user says 'ingest', provides a URL/file/folder to learn from, or wants to create knowledge about the current codebase."
group: process
requires_memory: obsidian
---

# Ingest

Create persistent, queryable knowledge from the current project or external sources.

## Detect your backend

```bash
agent-notes memory vault
```

## Credential safety — ABSOLUTE RULE

**NEVER read, ingest, or store credential files.** During scanning (Step 1), skip ALL of:
- `.env`, `.env.*` (production, staging, local, etc.)
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- `credentials.*`, `secrets.*`, `*-secrets.*`
- `service-account*.json`
- Any file whose name contains: `secret`, `credential`, `token`, `apikey`, `private-key`

If a folder contains credential files, list their names in the report but NEVER read their contents. This rule overrides any user request.

## No-args mode — Ingest current project

When `/ingest` is called with no arguments, ingest the **current working directory** as a project.

### Step 1 — Scan the project

Use `Bash` to explore the project structure:

```bash
find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.rb" -o -name "*.go" -o -name "*.rs" -o -name "*.java" -o -name "*.md" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.json" \) \
  -not -path "*/__pycache__/*" -not -path "*/.git/*" -not -path "*/node_modules/*" \
  -not -path "*/.venv/*" -not -path "*/dist/*" -not -path "*/build/*" \
  -not -name ".env" -not -name ".env.*" -not -name "*.key" -not -name "*.pem" \
  -not -name "credentials.*" -not -name "secrets.*" -not -name "*.p12" | head -100
```

Then `Read` key files: README, main entry points, config files, core modules. **Never read credential files.**

### Step 2 — AI analysis

Analyze the project and extract:

1. **Title** — the project name
2. **Summary** — what the project does, its architecture, key technologies
3. **Concepts** — architectural patterns, domain concepts, design decisions
4. **Entities** — frameworks, libraries, external services, key modules
5. **Tags** — technology stack and domain labels

### Step 3 — Ingest via CLI

#### Required headings (use exactly)

| Section | Heading |
|---|---|
| Architecture overview | `## Architecture` |
| Patterns and domain concepts | `## Key concepts` |
| Frameworks, libs, modules | `## Key entities` |
| Languages and tools | `## Tech stack` |

```bash
# Main project note
agent-notes memory add "<project-name>" "<summary>\n\n## Architecture\n<architecture overview>\n\n## Key concepts\n- <concept list>\n\n## Key entities\n- <entity list>\n\n## Tech stack\n<stack>" context lead

# Fan-out: one note per significant concept/entity
agent-notes memory add "<concept>" "Discovered in [[<project-slug>]]. <description.>" pattern lead
agent-notes memory add "<entity>" "Discovered in [[<project-slug>]]. <description.>" context lead
```

Map each fan-out note to the obsidian type that best fits:

| What it is | Obsidian type | Folder |
|---|---|---|
| A reusable technique or approach | `pattern` | Patterns/ |
| An architectural choice or rationale | `decision` | Decisions/ |
| A pitfall or anti-pattern | `mistake` | Mistakes/ |
| Background info, tool/lib reference | `context` | Context/ |

### Step 4 — Report

Report to the user:
- What was ingested (project name, file count, key findings)
- Concepts and entities extracted
- Number of notes created
- Confirm notes are linked to active session

## With arguments — Ingest external sources

When `/ingest` is called with a URL, file path, or folder path, ingest that specific source.

### Step 1 — Fetch the source

| Source type | How to read |
|---|---|
| URL | Use `WebFetch` tool to retrieve the page content |
| File | Use `Read` tool to read the file |
| Folder | Use `Bash` to list files (`find <path> -type f`), then `Read` key files. Skip: `__pycache__`, `.git`, `node_modules`, `.venv`, `dist`, `build`, `.egg-info` |

### Step 2 — AI analysis

Analyze the content and extract:

1. **Title** — a concise, descriptive name for this source
2. **Summary** — 2-5 sentence overview of what this source contains and why it matters
3. **Concepts** — key ideas, patterns, techniques, or abstractions
4. **Entities** — specific named things: tools, libraries, people, projects, APIs
5. **Tags** — categorization labels

### Step 3 — Ingest via CLI

```bash
# Main source note
agent-notes memory add "<title>" "<summary>\n\n## Key concepts\n- <concept list>\n\n## Key entities\n- <entity list>\n\n## Source\n<url or path>" context lead

# Fan-out: one note per concept/entity worth its own page
agent-notes memory add "<concept>" "Discovered in [[<title-slug>]]. <1-2 sentence description.>" pattern lead
agent-notes memory add "<entity>" "Discovered in [[<title-slug>]]. <1-2 sentence description.>" context lead
```

- No raw content archiving — your summary and fan-out notes ARE the stored knowledge. Be thorough in Step 2.
- Use `[[slug]]` wikilinks manually in note bodies for Obsidian graph view.

**Filtering rule**: Only create separate notes for concepts/entities worth retrieving independently in future sessions. Aim for 3-8 fan-out notes per source, not one per keyword.

**Deduplication rule**: Before creating fan-out notes, review the planned list for overlapping concepts. If two notes describe the same underlying design from different angles, merge them into one note covering both angles.

### Step 4 — Report

Report to the user:
- What was ingested (title, source type)
- Key concepts and entities extracted
- Number of notes created/updated
- Confirm notes are linked to active session

## Example — No-args (ingest CWD)

User: `/ingest`

1. `agent-notes memory vault` → obsidian, path: `/Users/me/Obsidian/agent-notes/projects/my-app`
2. Scan CWD: find 42 files (.py, .md, .toml)
3. Read README.md, pyproject.toml, key modules
4. Analyze: Title="my-app", Summary="A FastAPI service for...", Concepts=["dependency injection", "repository pattern"], Entities=["FastAPI", "PostgreSQL", "Alembic"]
5. Run `memory add` for main note + fan-out notes
6. Report: 1 main note, 2 concept notes, 3 entity notes created, linked to session

## Example — URL source

User: `/ingest https://docs.example.com/architecture`

1. `agent-notes memory vault` → obsidian
2. Fetch URL with WebFetch
3. Analyze content
4. Run `memory add` for main note + fan-out notes
5. Report: 4 notes created, linked to session

## Example — Folder source

User: `/ingest ./lib/payments`

1. `agent-notes memory vault` → obsidian
2. List files, read key modules
3. Analyze: Title="Payments Library", concepts, entities
4. Run `memory add` for main note + fan-out notes
5. Report results
