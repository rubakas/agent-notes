---
name: ingest
description: "Ingest a URL, local file, or folder into the wiki brain. Fetches content, extracts concepts and entities with AI analysis, and stores in the wiki. Use when user says 'ingest', provides a URL to study, or wants to add external knowledge."
group: memory
---

# Ingest

Ingest external sources into the wiki brain for persistent, queryable knowledge.

## Usage

The user provides one of:
- A **URL** (starts with `http://` or `https://`)
- A **file path** (path to a single file)
- A **folder path** (path to a directory)

## Workflow

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
3. **Concepts** — key ideas, patterns, techniques, or abstractions (e.g., "dependency injection", "event sourcing", "fan-out pattern")
4. **Entities** — specific named things: tools, libraries, people, projects, APIs (e.g., "PostgreSQL", "Karpathy", "wiki_backend.py")
5. **Tags** — categorization labels (e.g., "python", "architecture", "api")

### Step 3 — Ingest via CLI

Call the appropriate command:

**For a URL:**
```bash
agent-notes memory ingest-url "<url>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

**For a file:**
```bash
agent-notes memory ingest-file "<file_path>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

**For a folder:**
```bash
agent-notes memory ingest-folder "<folder_path>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

The CLI archives the raw content and creates the wiki source page. The AI-extracted concepts and entities are fanned out into their own wiki pages with cross-references.

### Step 4 — Report

After ingestion, report to the user:
- What was ingested (title, source type)
- Key concepts and entities extracted
- Number of wiki pages created/updated

## Example

User: `/ingest https://karpathy.github.io/2023/01/20/llm-wiki/`

1. Fetch URL with WebFetch
2. Analyze: Title="LLM Wiki by Karpathy", Summary="Proposes using LLMs to maintain personal knowledge wikis...", Concepts=["LLM Wiki", "knowledge management", "fan-out pattern"], Entities=["Andrej Karpathy"], Tags=["ai", "knowledge-management"]
3. Run: `agent-notes memory ingest-url "https://karpathy.github.io/2023/01/20/llm-wiki/" "Proposes using LLMs to maintain personal knowledge wikis..." "LLM Wiki,knowledge management,fan-out pattern" "Andrej Karpathy" "ai,knowledge-management"`
4. Report results
