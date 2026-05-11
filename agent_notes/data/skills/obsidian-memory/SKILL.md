---
name: obsidian-memory
description: "Save and retrieve agent memory in the Obsidian vault using agent-notes CLI. Defines the single record format for all memory notes. Use when saving decisions, patterns, or session state to the vault, or when ingesting URLs, files, or folders into the wiki brain."
group: process
---

# Obsidian Memory

Use when you need to persist a discovery, decision, or pattern for future sessions, or retrieve existing knowledge from the vault.

## Single rule for ALL records

This skill is the **single source of truth** for memory record format. The CLI implements these rules; do not deviate.

### Filename rule

All notes use `YYYY-MM-DD_<slug>.md`. The folder encodes the type — no type segment in the filename.

- **Session notes** (`type=session`): `YYYY-MM-DD_<session-id>.md`
  - Claude Code session ID: stem of the active JSONL at `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`
  - OpenCode: the session row's `id`
  - If no session ID can be detected, falls back to `YYYY-MM-DD_<slug>.md` (slug of the title)
- **All other types**: `YYYY-MM-DD_<slug>.md` where slug is the slugified title

**Collision rule**: if the target filename already exists, `_HHMMSS` is appended before `.md` (e.g. `2026-04-30_fix-foo_142231.md`).

A session note is **per-session**, not per-message. Re-running `memory add` with `type=session` for the same session appends an `## Update <UTC ISO>` block to the existing file rather than creating a new one.

### Frontmatter rule

Every record uses the same template. No `date:` field — only `created_at:`.

```yaml
---
created_at: 2026-04-28T19:30:35Z   # ISO 8601, UTC, "Z" suffix — REQUIRED
type: pattern                       # pattern|decision|mistake|context|session — REQUIRED
session: 2026-04-28_<session-id>   # wikilink target (no brackets); absent on session notes themselves
agent: lead                         # optional
---
```

After the frontmatter, every note body is followed by:

```markdown
## Related

(empty initially; Obsidian links can be added manually)
```

Session notes additionally grow a `## Linked notes` section that the CLI populates automatically when non-session notes are written during the same session.

### Time rule

All timestamps everywhere are **UTC**. Local time is never written. The CLI uses `datetime.now(timezone.utc)`.

## Saving a memory

Always use the CLI — never write vault files directly:

```bash
agent-notes memory add "<title>" "<body>" [type] [agent]
```

**Types:**
- `pattern` — reusable solution or technique discovered in the codebase
- `decision` — architectural choice with rationale
- `mistake` — recurring error to avoid
- `context` — project background, constraints, stakeholder notes
- `session` — current session's running log (one file per session, appended on each call)

**Agent:** your agent name (`lead`, `coder`, `reviewer`, etc.)

Examples:
```bash
agent-notes memory add "Rails enum prefix" \
  "Always use _prefix: true to avoid method name collisions" \
  pattern coder

agent-notes memory add "Auth middleware rewrite rationale" \
  "Driven by legal/compliance requirements around session token storage, not tech debt" \
  decision lead
```

## What to save

Save when you discover something **non-obvious** that would cost future sessions time to re-derive:

- A hidden constraint or invariant in the codebase
- A decision with non-obvious tradeoffs
- A recurring mistake the project is prone to
- Project-specific conventions that differ from standard practice

Do NOT save:
- Things derivable by reading the code (`git log`, `grep`)
- Standard framework behavior
- In-progress task state (use tasks for that)
- Information already in CLAUDE.md or docs

## Retrieving memories

```bash
agent-notes memory list              # all notes by category
agent-notes memory show <agent>      # one agent's notes
agent-notes memory vault             # confirm storage and path
```

The vault is structured as:
```
vault/agent-notes/
├── Patterns/     — reusable solutions        YYYY-MM-DD_<slug>.md
├── Decisions/    — architectural choices     YYYY-MM-DD_<slug>.md
├── Mistakes/     — errors to avoid           YYYY-MM-DD_<slug>.md
├── Context/      — project background        YYYY-MM-DD_<slug>.md
├── Sessions/     — one file per session      YYYY-MM-DD_<session-id>.md
└── Index.md      — chronological list, newest first
```

The root `agent-notes/` is shared across all projects — there is no per-project subfolder.

## Regenerate the index

After any manual edits in Obsidian:
```bash
agent-notes memory index
```

## Updating these rules

If you change a rule above (filename pattern, frontmatter field, time format), update **both**:
1. This file (`agent_notes/data/skills/obsidian-memory/SKILL.md`)
2. `agent_notes/services/memory_backend.py` — the CLI that implements them

The two must stay in sync. The skill is the canonical statement; the CLI is the enforcer.

## Cadence rule

The session note is updated on every meaningful state change. Specifically:
- Session start: one `memory add ... session lead` call that establishes the note.
- After every dispatched agent's verdict (reviewer/coder/test-writer return): one append covering what landed.
- Before reporting a phase done: one append summarizing the phase outcome.
- On user redirect or scope change: one append capturing the new direction and rationale.

Skipping any of these makes the session note stale and breaks cross-session reconstruction. The Done Gate in `global-claude.md` enforces this for the lead; team agents follow the read-before-work side via the next section.

## Auto-linking rule

Whenever a session is active (Claude Code session ID detectable) and a non-session note is written, the CLI **automatically** appends a wikilink line to the session note's `## Linked notes` section:

```
- [[<filename-stem>]] — <type> — <title>
```

This is done in the same `agent-notes memory add` call — no second call is needed. The operation is idempotent: if the link already exists, it is not duplicated.

The session note becomes the navigable hub for everything written during the session without any extra work from the agent.

**Backend conditional**: auto-linking only applies when the configured memory storage is Obsidian. On local storage, there are no wikilinks and this step is a no-op.

## Plan-mirror rule (Obsidian storage only)

After every Claude Code `ExitPlanMode` invocation:

1. Check the configured memory storage. The SKILL substitutes `{{MEMORY_PATH}}` at build time; if it resolves to a path under a vault, the storage is Obsidian.
2. If Obsidian: write the plan content as a Decision note via `agent-notes memory add "<plan-title>" "<plan-body>" decision lead`. The local plan file at `~/.claude/plans/<file>.md` stays for harness compatibility.
3. If local storage or memory disabled: skip the mirror entirely. The plan stays at its harness path; nothing else needs to happen.

When mirrored, the new Decision participates in the Linking rule above — the active session note (if any) gets a wikilink to it.

**Why mirror, not move**: Claude Code's plan-mode requires the local file to exist (the harness reads it on resume and ExitPlanMode writes to it). The Decision note in Obsidian is the navigable canonical record; the local file is the harness's working copy.

## When to use Obsidian storage vs Wiki storage

| Choose Obsidian when... | Choose Wiki when... |
|---|---|
| You want category-based organization (Patterns, Decisions, Mistakes) | You want knowledge that compounds (sources → concepts → synthesis) |
| You need auto-linking between session notes and discoveries | You need the ingest → query → lint workflow |
| You browse notes visually in Obsidian with backlinks | You're building a team knowledge base |
| Your memory is about process (what worked, what failed) | Your memory is about domain knowledge (how things work) |

**Process vs domain memory:**

Obsidian storage focuses on **process memory** — tracking decisions, patterns, and mistakes across sessions. It answers "What did we learn?" and "Why did we choose this?"

Wiki storage focuses on **domain memory** — compiling source material into a structured, cross-referenced knowledge base that compounds over time. It answers "How does this work?" and "What are the facts?"

## Read protocol (for team agents)

Any dispatched agent that needs context about the project's current state — recent decisions, patterns, mistakes, or what the lead has done so far — MUST read the Obsidian vault before starting work:

1. Read `<vault>/Index.md` to see what categories have content and which notes are most recent.
2. If the task is about an in-flight initiative, read the current session note (`<vault>/Sessions/<session-id>.md`) for the latest progress.
3. If the task involves a category (decisions, patterns, mistakes, context), read the 3–5 most recent files in that folder.

The vault path is substituted into agent prompts at build time as `{{MEMORY_PATH}}`. If `{{MEMORY_PATH}}` resolves to "disabled", skip this protocol — memory is not configured.

Agents do NOT need bash access for this; the vault is plain Markdown readable with the `Read` tool.

## Ingest workflow

Ingest external sources into the wiki brain for persistent, queryable knowledge.

The user provides one of:
- A **URL** (starts with `http://` or `https://`)
- A **file path** (path to a single file)
- A **folder path** (path to a directory)

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

Call the single ingest command regardless of source type:

```bash
agent-notes memory ingest "<title>" "<summary>" "<concepts_csv>" "<entities_csv>" "<tags_csv>"
```

This creates the source page and fans out to concept and entity pages with cross-references. Note: raw content archiving is not available via CLI — the AI summary is the stored knowledge.

### Step 4 — Report

After ingestion, report to the user:
- What was ingested (title, source type)
- Key concepts and entities extracted
- Number of wiki pages created/updated

### Example

User: `/ingest https://karpathy.github.io/2023/01/20/llm-wiki/`

1. Fetch URL with WebFetch
2. Analyze: Title="LLM Wiki by Karpathy", Summary="Proposes using LLMs to maintain personal knowledge wikis...", Concepts=["LLM Wiki", "knowledge management", "fan-out pattern"], Entities=["Andrej Karpathy"], Tags=["ai", "knowledge-management"]
3. Run: `agent-notes memory ingest "LLM Wiki by Karpathy" "Proposes using LLMs to maintain personal knowledge wikis..." "LLM Wiki,knowledge management,fan-out pattern" "Andrej Karpathy" "ai,knowledge-management"`
4. Report results

### No-args mode — Karpathy compile operation

When `/ingest` is called with no arguments, it triggers the Karpathy LLM Wiki **compile operation**: read raw sources, write rich wiki pages, cross-reference everything.

**Step 1 — Scan**:
```bash
agent-notes memory ingest
```
Lists unprocessed raw file groups.

**Step 2 — Inventory existing pages**: Read existing concept/entity pages. Identify stubs (body is just "Referenced from source") that need compilation.

**Step 3 — Group by domain**: Cluster related concepts into batches of 5-10 for focused compilation. Examples:
- Payments: ACH processing, wire approvals, reconciliation, mass payments
- Real estate: deal management, construction draws, loan servicing, extensions
- Integrations: DocuSign, Plaid, Slack, HubSpot

**Step 4 — Dispatch wiki-compiler**: For each domain batch, dispatch the `wiki-compiler` agent:
```
wiki-compiler: "Compile these concepts from raw source material: [concept list].
Wiki root: <path>. Raw chunks: portal-domcap-001.md through -017.md.
Read the code, write rich Wikipedia-style pages."
```

The wiki-compiler greps raw chunks for relevant code, reads it, and writes rich pages via `agent-notes memory add`.

**Step 5 — Synthesis**: After all batches complete, create synthesis pages for cross-cutting themes:
- "Payment Architecture" — how ACH and wire flows connect
- "Deal Lifecycle" — from origination to payoff
- "Notification System" — email, Slack, task assignment integration

Use: `agent-notes memory add "<title>" "<body>" synthesis lead`

**Step 6 — Lint**: Run `agent-notes memory lint` to verify wiki health — no broken links, orphan pages, or stubs remaining.
