---
name: ingest
description: "Ingest the current project or external sources (URLs, files, folders) into the knowledge base. Adapts to the active memory backend: wiki (Karpathy flow with raw archiving, fan-out, cross-ref) or obsidian (category-mapped notes with session linking). Use when user says 'ingest', provides a URL/file/folder to learn from, or wants to create knowledge about the current codebase."
group: process
requires_memory: obsidian,wiki
---

# Ingest

Create persistent, queryable knowledge from the current project or external sources. Adapts to the active memory backend.

## Backend differences

| Capability | Wiki (Karpathy) | Obsidian (session/project) |
|---|---|---|
| Purpose | Domain knowledge base that compounds over time | Process memory — decisions, patterns, context |
| Raw content archiving | Yes (`raw/` folder, immutable) | No — the AI summary IS the stored knowledge |
| Structured fan-out | source → concepts → entities → synthesis | context → pattern/decision/mistake notes |
| Auto cross-referencing | Bidirectional `[[wikilinks]]` | Session auto-linking only |
| Query / search | Yes (`agent-notes memory query`) | No |
| Lint / health check | Yes (`agent-notes memory lint`) | No |
| Page types | sources, concepts, entities, synthesis, sessions | Patterns, Decisions, Mistakes, Context, Sessions |

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
3. **Concepts** — architectural patterns, domain concepts, design decisions (e.g., "event sourcing", "CQRS", "wiki backend", "tree-sitter extraction")
4. **Entities** — frameworks, libraries, external services, key modules (e.g., "FastAPI", "PostgreSQL", "wiki_backend.py", "Graphify")
5. **Tags** — technology stack and domain labels

### Step 3 — Ingest via CLI

#### Wiki backend

Pass the **folder path** as the first argument so the CLI archives all source files into `raw/`:

```bash
agent-notes memory ingest "<folder-path>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

For no-args mode (CWD), use `.` as the folder path:

```bash
agent-notes memory ingest "." "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

The CLI auto-detects folder paths, scans all files recursively (respecting `.gitignore` and credential filters), archives raw content to `raw/`, creates a source page, and fans out to concept/entity stub pages.

### Step 3.5 — Compile stubs (wiki backend only)

After ingestion, dispatch the `wiki-compiler` agent to compile each stub into a rich, Wikipedia-style page. The compiler reads the raw source material and writes detailed content.

For each concept and entity stub created in Step 3, dispatch wiki-compiler:

```
Agent(wiki-compiler): "Compile the wiki page at <stub-path>. Read the raw source material referenced from [[<source-page>]] and write a rich, detailed page with domain logic, relationships, and cross-references."
```

Run up to 3 wiki-compiler agents **in parallel** for efficiency. Each compiler reads from `raw/` and writes to the stub page.

#### Obsidian backend

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
- Backend used
- Concepts and entities extracted
- Number of notes/pages created
- For wiki: number of stubs compiled by wiki-compiler
- For obsidian: confirm notes are linked to active session

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

#### Wiki backend

For **folder** sources, pass the folder path as the first argument (enables raw archiving):

```bash
agent-notes memory ingest "<folder-path>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

For **URL** and **file** sources, pass the title:

```bash
agent-notes memory ingest "<title>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

After ingestion, dispatch wiki-compiler on each stub (same as Step 3.5 in no-args mode).

#### Obsidian backend

```bash
# Main source note
agent-notes memory add "<title>" "<summary>\n\n## Key concepts\n- <concept list>\n\n## Key entities\n- <entity list>\n\n## Source\n<url or path>" context lead

# Fan-out: one note per concept/entity worth its own page
agent-notes memory add "<concept>" "Discovered in [[<title-slug>]]. <1-2 sentence description.>" pattern lead
agent-notes memory add "<entity>" "Discovered in [[<title-slug>]]. <1-2 sentence description.>" context lead
```

**Important differences from wiki backend:**
- No raw content archiving — your summary and fan-out notes ARE the stored knowledge. Be thorough in Step 2.
- No bidirectional cross-referencing — use `[[slug]]` wikilinks manually in note bodies for Obsidian graph view.
- No `query` or `lint` — notes are browsable via Obsidian client or `memory list` / `memory show`.

**Filtering rule**: Only create separate notes for concepts/entities worth retrieving independently in future sessions. Aim for 3-8 fan-out notes per source, not one per keyword.

**Deduplication rule**: Before creating fan-out notes, review the planned list for overlapping concepts. If two notes describe the same underlying design from different angles, merge them into one note covering both angles. One thorough note is better than two partial ones.

### Step 4 — Report

Report to the user:
- What was ingested (title, source type)
- Backend used (wiki or obsidian)
- Key concepts and entities extracted
- Number of notes created/updated
- For wiki: mention raw content is archived and stubs can be compiled
- For obsidian: confirm notes are linked to active session

## Example — No-args (ingest CWD)

User: `/ingest`

1. `agent-notes memory vault` → wiki, path: `/Users/me/Obsidian/knowledge`
2. Scan CWD: find 42 files (.py, .md, .toml)
3. Read README.md, pyproject.toml, key modules
4. Analyze: Title="my-app", Summary="A FastAPI service for...", Concepts=["dependency injection", "repository pattern"], Entities=["FastAPI", "PostgreSQL", "Alembic"]
5. `agent-notes memory ingest "." "A FastAPI service for..." "dependency injection,repository pattern" "FastAPI,PostgreSQL,Alembic" "python,api,backend"`
6. Dispatch wiki-compiler on each stub (up to 3 in parallel)
7. Report: 1 source, 2 compiled concepts, 3 compiled entities. Raw archived.

## Example — URL source

User: `/ingest https://docs.example.com/architecture`

1. `agent-notes memory vault` → obsidian
2. Fetch URL with WebFetch
3. Analyze content
4. Run `memory add` for main note + fan-out notes
5. Report: 4 notes created, linked to session

## Example — Folder source

User: `/ingest ./lib/payments`

1. `agent-notes memory vault` → wiki
2. List files, read key modules
3. Analyze: Title="Payments Library", concepts, entities
4. `agent-notes memory ingest "./lib/payments" "..." "ACH,wire transfers" "Stripe,Plaid" "payments,fintech"`
5. Dispatch wiki-compiler on each stub
6. Report results
