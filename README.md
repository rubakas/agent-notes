# agent-notes

AI agent configuration manager for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [OpenCode](https://github.com/opencode-ai/opencode).

Configures a Lead agent (Opus) that orchestrates a team of 19 specialized subagents across three model tiers — so Opus 4.6 plans and reasons, Sonnet 4.6 executes, and Haiku 4.5 explores.

## Quick Start

```bash
pip install agent-notes
agent-notes install    # interactive wizard guides you through setup
agent-notes doctor
```

## What's Included

| Component | Description |
|-----------|-------------|
| **Skills** | 42+ on-demand knowledge modules (Rails, Docker, Git, Kamal, Process) |
| **Agents** | 19 specialized AI subagents with hierarchical model strategy |
| **Rules** | Global instructions, code quality, and safety guardrails |
| **Config** | Global instructions for Claude Code, OpenCode, and GitHub Copilot |

## Install Methods

There are three ways to use agent-notes. Pick the one that matches your intent.

### 1. Python package — PyPI (recommended)

```bash
pip install agent-notes
# or
pipx install agent-notes
agent-notes install
```

Update anytime:

```bash
pip install --upgrade agent-notes && agent-notes install
# or
pipx upgrade agent-notes && agent-notes install
```

### 2. Python package — from local build (developers)

```bash
git clone https://github.com/rubakas/agent-notes.git
cd agent-notes
python -m build                    # produces dist/*.whl
pipx install dist/*.whl            # or pip install --user dist/*.whl
agent-notes install
```

Iteration loop: edit source → `python -m build` → `pipx reinstall dist/*.whl`. Not editable mode. Not `pip install -e .`.

### 3. Plugin — limited functionality

- **Claude Code**: install via the Claude Code plugin marketplace or copy/symlink `.claude-plugin/` into `~/.claude/plugins/agent-notes/`.
- **OpenCode**: copy or symlink `.claude-plugin/` into `~/.config/opencode/plugins/agent-notes/` and add `"plugin": ["agent-notes"]` to `opencode.json`.

The plugin runs a `session.start` hook that surfaces agent-notes context to the CLI session. It does **not** include the full `agent-notes` CLI (wizard, doctor, config, memory, etc.). For those, use install method 1 or 2.

### API keys

Provider API keys live in `~/.agent-notes/credentials.toml` (mode 0600, never committed). Add or update via:

```bash
agent-notes config providers
```

The wizard prompts for the key with hidden input; agent-notes never logs or prints the value. To check whether a provider is configured without exposing the key:

```bash
agent-notes config provider openrouter   # prints "configured" or "no key"
```

## CLI Reference

```
agent-notes <command> [options]
```

| Command | Description |
|---------|-------------|
| `install [--local] [--copy] [--reconfigure]` | Interactive wizard or direct install |
| `uninstall [--local \| --global]` | Remove installed components (both scopes by default) |
| `doctor [--local] [--fix]` | Check installation health |
| `info` | Show status and component counts |
| `list [clis\|models\|roles\|agents\|skills\|rules\|all]` | List engine components or installed |
| `set role <role> <model> [--cli <cli>]` | Change model for a role (Phase 10+) |
| `regenerate [--cli <cli>]` | Rebuild files from state.json (Phase 10+) |
| `validate` | Lint source configuration files |
| `memory [list\|size\|show\|reset\|export\|import] [name]` | Manage agent memory |
| `cost-report` | Show session cost breakdown by agent and model |

### Supported platforms

| Platform | Install target | Config format |
|----------|---------------|---------------|
| **Claude Code** | `~/.claude/` | YAML frontmatter + Markdown prompts |
| **OpenCode** | `~/.config/opencode/` | YAML frontmatter + Markdown prompts |
| **GitHub Copilot** | `~/.github/` | `copilot-instructions.md` |

### Quick usage examples

```bash
# Interactive install (recommended)
agent-notes install

# Direct install (scripted)
agent-notes install --local --copy

# Check health and fix issues
agent-notes doctor --fix

# Manage agent memory
agent-notes memory list
agent-notes memory add "Rails enum prefix" \
  "Always use _prefix: true to avoid method name collisions" \
  pattern coder
```

## Agent Team

Specialized subagents with hierarchical model strategy: **Opus 4.6 reasons, Sonnet 4.6 executes, Haiku 4.5 scouts.**

| Agent | Role | Model Tier | Purpose |
|---|---|---|---|
| lead | orchestrator | opus | Plans, coordinates, verifies — the team lead |
| architect | reasoner | opus | System design, module boundaries, refactor planning |
| debugger | reasoner | opus | Complex bug investigation, root-cause analysis |
| coder | worker | sonnet | Implementation, file edits, bug fixes |
| reviewer | worker | sonnet | Code quality, readability, correctness |
| security-auditor | worker | sonnet | Auth, injection, XSS, secrets exposure |
| test-writer | worker | sonnet | Creates tests for any framework |
| test-runner | worker | sonnet | Diagnoses and fixes failing tests |
| system-auditor | worker | sonnet | Duplication, dead code, coupling, complexity |
| database-specialist | worker | sonnet | Schema design, indexes, query performance |
| performance-profiler | worker | sonnet | Response times, memory, bundle size |
| api-reviewer | worker | sonnet | REST conventions, versioning, backward compatibility |
| devops | worker | sonnet | Docker, CI/CD, deployment, infrastructure |
| devil | worker | sonnet | Devil's advocate — challenges plans and assumptions |
| integrations | worker | sonnet | OAuth, webhooks, API clients, SSO |
| refactorer | worker | sonnet | Extracts methods, reduces duplication, improves naming |
| explorer | scout | haiku | Fast file discovery, pattern search |
| analyst | scout | haiku | Requirements translation, acceptance criteria |
| tech-writer | scout | haiku | READMEs, API docs, changelogs |

**4 roles, 19 agents, 3 model tiers.** The tiered model strategy optimizes cost: Opus reasons ($15/1M tokens), Sonnet executes ($3/1M), Haiku scouts ($0.80/1M).

## Architecture

agent-notes is a 4-layer engine (domain / registries / services / commands). All extensible content (CLIs, models, roles, agents, skills, rules) lives in `agent_notes/data/` as YAML — adding a new CLI/model/role is a YAML drop, no Python changes. Context is loaded in tiers: always-loaded (CLAUDE.md, rules, skill catalog), lazy-loaded (full skill content, agent prompts), and pull-based (memory notes). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ADD_CLI.md](docs/ADD_CLI.md), [docs/ADD_MODEL.md](docs/ADD_MODEL.md), [docs/ADD_ROLE.md](docs/ADD_ROLE.md).

## Improved Claude Code workflows

Four failure modes that derail AI-assisted development, and the skills that address them.

| Failure mode | What goes wrong | Skills that help |
|---|---|---|
| **Misalignment** | Claude starts building before the problem is resolved | `/grill-me`, `/grill-with-docs` |
| **Verbosity** | Responses are bloated; context window fills with noise | `/caveman`, `/setup-project-context` |
| **Broken code** | Claude codes without a feedback loop or evidence trail | `/tdd` (improved), `/debugging-protocol` (improved) |
| **Ball of mud** | Architecture drifts; modules grow shallow and tangled | `/improve-codebase-architecture`, `/zoom-out` |

- `/grill-me` — interview the user until the problem is fully resolved before touching code
- `/grill-with-docs` — same, but cross-references CONTEXT.md and ADRs and updates them inline
- `/caveman` — ultra-compressed reply mode (~75% token savings) for rapid iteration
- `/setup-project-context` — bootstraps a CONTEXT.md domain glossary (ubiquitous language)
- `/tdd` — RED-GREEN-REFACTOR with tracer-bullet vertical slices; horizontal-slicing anti-pattern added
- `/debugging-protocol` — Phase 1 rewritten as "build a feedback loop first" with 9 strategies
- `/improve-codebase-architecture` — deletion test to find shallow modules; surfaces deepening opportunities
- `/zoom-out` — quick orientation map of an unfamiliar code area

## Skills

42+ on-demand knowledge modules across Rails, Docker, Kamal, Git, and Process. Run `agent-notes list skills` for the current list, or browse `agent_notes/data/skills/`.

The session context hook auto-generates a skill index from SKILL.md frontmatter at install time, so agents always know what skills are available without loading full skill content. This keeps context overhead low while maintaining skill discoverability.

### Using skills in Claude Code / OpenCode

```
Use the rails-models skill to help with this association
Load the docker-compose skill for multi-service setup
```

## Agent Memory

Agents accumulate knowledge across sessions using one of four backends, chosen during `agent-notes install`.

### Backends

| Backend | Storage | Best for |
|---------|---------|----------|
| **Local** | `~/.claude/agent-memory/<agent>/` — plain markdown per agent | Simple setup, no extra tools |
| **Obsidian** | Category vault with YAML frontmatter and `[[wikilinks]]` | Visual browsing, backlinks, Dataview queries |
| **Wiki** | Structured wiki with page types and versioning | Team knowledge bases, compounding knowledge |
| **None** | Disabled — no files written | Stateless or shared machines |

### Session tracking by backend

| Feature | Local | Obsidian | Wiki |
|---|---|---|---|
| Storage location | `~/.claude/agent-memory/<agent>/` | Obsidian vault with categories | Structured wiki with page types |
| Note types | Flat markdown per agent | `pattern`, `decision`, `mistake`, `context`, `session` | `source`, `concept`, `entity`, `synthesis`, `session` |
| Session tracking | None | Auto-created session notes with `## Linked notes` | Session pages in `wiki/sessions/` |
| Cross-referencing | None | `[[wikilinks]]` auto-appended to session notes | Markdown links maintained by LLM |
| Key operations | read/write | add, list, show, reset, export, import | ingest, query, lint + add, list, show |
| Best for | Simple setup, no extra tools | Visual browsing, backlinks, Dataview queries | Team knowledge bases, compounding knowledge |

**Obsidian backend** — Uses category directories (`Patterns/`, `Decisions/`, `Mistakes/`, `Context/`, `Sessions/`). When you write a non-session note during an active session, the CLI auto-links it to the session note via `[[wikilinks]]`. Plans are mirrored as Decision notes.

**Wiki backend** — Implements Karpathy's LLM Wiki pattern (v1). Structure: `raw/` for immutable source material, `wiki/` for LLM-maintained pages organized into `sources/`, `concepts/`, `entities/`, `synthesis/`, `sessions/`. Three key operations:
- **ingest** — Process source material, extract key info, update entity/concept pages, append to log
- **query** — Search wiki pages, synthesize answers with citations, optionally file answers back as new pages
- **lint** — Health-check for contradictions, stale claims, orphan pages, missing cross-references

### Obsidian setup

Run `agent-notes install` and pick Obsidian when prompted. The wizard auto-detects existing vaults under `~/Documents`, `~/Desktop`, and `~`. To initialize the vault structure:

```bash
agent-notes memory init
```

The installed `CLAUDE.md` already points agents to your vault. At the start of a session Claude reads `Index.md`; at the end it can save insights with `agent-notes memory add`.

### Memory commands

```bash
agent-notes memory init                    # create folder structure and Index.md
agent-notes memory list                    # list all notes (by category or agent)
agent-notes memory vault                   # show backend, path, and init status
agent-notes memory index                   # regenerate Index.md
agent-notes memory add <title> <body> [type] [agent] [project]   # type: pattern|decision|mistake|context|session
agent-notes memory show <agent>            # show one agent's notes (local backend)
agent-notes memory reset [agent]           # clear memory (confirmation required)
agent-notes memory export                  # back up to memory-backup/
agent-notes memory import                  # restore from memory-backup/
agent-notes install --reconfigure          # switch backends
```

### Note format (Obsidian backend)

Every note agent-notes writes includes YAML frontmatter for filtering and Dataview queries:

```markdown
---
created_at: 2026-04-28T19:30:35Z
type: pattern
agent: coder
project: rubakas
tags: [rails, models]
---

# Rails Enum Prefix

Always use `_prefix: true` with Rails enums to avoid method name collisions.
```

## Inspired by

- [Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — The wiki memory backend implements his compile-once, query-forever knowledge pattern with structured page types and three core operations (ingest, query, lint)
- [Matt Pocock's skills repo](https://github.com/mattpocock/skills) — Skill format (SKILL.md per directory), failure-mode table (misalignment, verbosity, broken code, architectural degradation), and several core skills (tdd, grill-me, grill-with-docs, improve-codebase-architecture, zoom-out, caveman)

## Development

Python 3.10+ required. Build from source and run tests:

```bash
python -m build && pipx install dist/*.whl
python3 -m pytest tests/
```

Run `agent-notes build` after editing `agent_notes/data/` files, and `agent-notes validate` before committing.

Tests live in `tests/functional/` (unit), `tests/integration/` (build output), and `tests/plugins/` (artifact validation).

## Contributing

When adding new content:

1. **Edit source files** — all changes go in `agent_notes/data/` directory
2. **Run build** — `agent-notes build` to generate platform configs
3. **Validate** — `agent-notes validate` before committing
4. **Keep it generic** — remove app-specific references
5. **Show examples** — include code samples with explanations
6. **Stay modular** — each skill should be independently usable
7. **Stay concise** — agent prompts under 60 lines

See [docs/](docs/) for full guidelines.

## License

MIT
