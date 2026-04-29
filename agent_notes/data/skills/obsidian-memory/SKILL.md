---
name: obsidian-memory
description: "Save and retrieve agent memory in the Obsidian vault using agent-notes CLI. Defines the single record format for all memory notes."
group: process
---

# Obsidian Memory

Use when you need to persist a discovery, decision, or pattern for future sessions, or retrieve existing knowledge from the vault.

## Single rule for ALL records

This skill is the **single source of truth** for memory record format. The CLI implements these rules; do not deviate.

### Filename rule

- **Session notes** (`type=session`): filename is `<session-id>.md`
  - Claude Code: stem of the active JSONL at `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`
  - OpenCode: the session row's `id`
- **All other types**: filename is `<UTC-YYYY-MM-DD-HH-MM-SS>-<slug>.md`

A session note is **per-session**, not per-message. Re-running `memory add` with `type=session` for the same session appends an `## Update <UTC ISO>` block to the existing file rather than creating a new one. If no session ID can be detected (e.g. invoked outside a CLI session), the note falls back to the timestamp+slug filename rule.

### Frontmatter rule

Every record has this frontmatter, in this order. No `date:` field — only `created_at:`.

```yaml
---
created_at: 2026-04-28T19:30:35Z   # ISO 8601, UTC, "Z" suffix — REQUIRED
type: pattern                       # pattern|decision|mistake|context|session — REQUIRED
session_id: <id>                    # REQUIRED when detectable (Claude Code / OpenCode session); omitted otherwise
agent: lead                         # optional
project: <name>                     # optional
tags: [a, b]                        # optional
---
```

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
agent-notes memory vault             # confirm backend and path
```

The vault is structured as:
```
vault/
├── Patterns/     — reusable solutions
├── Decisions/    — architectural choices
├── Mistakes/     — errors to avoid
├── Context/      — project background
└── Sessions/     — one file per session, named <session-id>.md
```

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

## Linking rule

Whenever a session is active and a non-session note is written (Decision / Pattern / Mistake / Context), the session note must be appended with a wikilink to it within the same logical operation:

1. Write the new Decision / Pattern / Mistake / Context note via `agent-notes memory add ... <type> lead`. Capture the returned path.
2. Append a single line to the session note via a second `agent-notes memory add "<session-title>" "Linked: [[<filename-stem>]] — <type> — <one-line-why>" session lead`.

The cadence rule already mandates one append per phase outcome; this rule layers wikilinks onto that append. Result: the session note becomes the navigable hub for everything written during the session.

**General notes (project-truths, not tied to one session) do NOT get linked.** Examples:
- A Pattern about Rails enum prefix: applies forever, lives in `Patterns/`, NOT referenced from any session note.
- A Decision about choosing PostgreSQL: applies forever, lives in `Decisions/`, NOT referenced from a session note.

**Judgment call**: if the note explains "what we did today and why" → link it from the session note. If the note explains "how the project works in general" → don't link it.

**Backend conditional**: this rule only applies when the configured memory backend is Obsidian. On the local backend (no vault, no wikilinks), skip the linking step — the cadence rule alone is enough.

## Plan-mirror rule (Obsidian backend only)

After every Claude Code `ExitPlanMode` invocation:

1. Check the configured memory backend. The SKILL substitutes `{{MEMORY_PATH}}` at build time; if it resolves to a path under a vault, the backend is Obsidian.
2. If Obsidian: write the plan content as a Decision note via `agent-notes memory add "<plan-title>" "<plan-body>" decision lead`. The local plan file at `~/.claude/plans/<file>.md` stays for harness compatibility.
3. If local backend or memory disabled: skip the mirror entirely. The plan stays at its harness path; nothing else needs to happen.

When mirrored, the new Decision participates in the Linking rule above — the active session note (if any) gets a wikilink to it.

**Why mirror, not move**: Claude Code's plan-mode requires the local file to exist (the harness reads it on resume and ExitPlanMode writes to it). The Decision note in Obsidian is the navigable canonical record; the local file is the harness's working copy.

## Read protocol (for team agents)

Any dispatched agent that needs context about the project's current state — recent decisions, patterns, mistakes, or what the lead has done so far — MUST read the Obsidian vault before starting work:

1. Read `<vault>/Index.md` to see what categories have content and which notes are most recent.
2. If the task is about an in-flight initiative, read the current session note (`<vault>/Sessions/<session-id>.md`) for the latest progress.
3. If the task involves a category (decisions, patterns, mistakes, context), read the 3–5 most recent files in that folder.

The vault path is substituted into agent prompts at build time as `{{MEMORY_PATH}}`. If `{{MEMORY_PATH}}` resolves to "disabled", skip this protocol — memory is not configured.

Agents do NOT need bash access for this; the vault is plain Markdown readable with the `Read` tool.
