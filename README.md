# agent-notes

AI agent configuration manager for Claude Code and OpenCode — orchestrates a team of 19 specialized subagents across three model tiers.

## Quick Start

```bash
pip install agent-notes
agent-notes install    # interactive wizard guides you through setup
agent-notes doctor
```

**What's Included**
- 19 specialized AI subagents (Opus reasons, Sonnet executes, Haiku explores)
- 42+ on-demand skills (Rails, Docker, Git, Kamal, Process)
- Global rules and guardrails
- Agent memory with 3 storage options (Local, Obsidian, Wiki)
- Configuration for Claude Code, OpenCode, and GitHub Copilot

---

<details>
<summary>Installation</summary>

### PyPI (recommended)

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

### Local build (developers)

```bash
git clone https://github.com/rubakas/agent-notes.git
cd agent-notes
python -m build                    # produces dist/*.whl
pipx install dist/*.whl            # or pip install --user dist/*.whl
agent-notes install
```

Iteration loop: edit source → `python -m build` → `pipx reinstall dist/*.whl`. Not editable mode. Not `pip install -e .`.

### Plugin (limited functionality)

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

</details>

---

<details>
<summary>Agent Team</summary>

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

### Delegation rules

- **lead** — Plans, coordinates, and verifies across the team
- **architect** / **debugger** — Deep reasoning for complex design and debugging
- **coder** — All file edits and implementation work
- **reviewer** — Code quality checks after implementation
- **security-auditor** — Auth, input handling, data access
- **test-writer** — Creates tests; **test-runner** diagnoses and fixes failures
- **system-auditor** — Duplication, dead code, architectural issues
- **database-specialist** — Schema design, queries, indexes
- **performance-profiler** — Latency, memory, bundle size
- **api-reviewer** — REST conventions, versioning, backward compatibility
- **devops** — Infrastructure, CI/CD, Docker
- **integrations** — OAuth, webhooks, API clients
- **refactorer** — Extraction, duplication, naming
- **explorer** — Fast discovery and pattern search
- **analyst** — Requirements and acceptance criteria
- **tech-writer** — Documentation, READMEs, API docs
- **devil** — Challenges assumptions and plans

</details>

---

<details>
<summary>Memory Storage</summary>

Agents accumulate knowledge across sessions using one of three storage options, chosen during `agent-notes install`.

### Storage comparison

| Feature | Local | Obsidian | Wiki |
|---|---|---|---|
| Location | `~/.claude/agent-memory/` | Obsidian vault | Obsidian vault |
| Project scoping | No | Yes (per CWD) | Yes (per CWD) |
| Organization | Per-agent folders | Categories (Patterns, Decisions, etc.) | Wiki pages (sources, concepts, entities) |
| Best for | Simple setup | Process memory, visual browsing | Domain knowledge, team knowledge bases |

### Local (default)

Plain markdown storage in `~/.claude/agent-memory/<agent>/` — one folder per agent, no project scoping or cross-referencing. Simplest setup, no external tools needed.

**Commands:**
```bash
agent-notes memory list                  # list all notes by agent
agent-notes memory show <agent>          # show one agent's notes
agent-notes memory size                  # disk usage
agent-notes memory reset [agent]         # clear memory (confirmation required)
agent-notes memory export                # back up to memory-backup/
agent-notes memory import                # restore from memory-backup/
```

### Obsidian (per-project sessions)

Category vault with YAML frontmatter and `[[wikilinks]]`. Auto-creates a folder per project (derived from current working directory name) and organizes notes into categories: `Patterns/`, `Decisions/`, `Mistakes/`, `Context/`, `Sessions/`.

**Structure:**
```
<vault-root>/<project-name>/
├── Patterns/
├── Decisions/
├── Mistakes/
├── Context/
├── Sessions/
└── Index.md
```

**Note types:** pattern, decision, mistake, context, session

**Key features:**
- YAML frontmatter for filtering and Dataview queries (created_at, type, agent, project, tags)
- Auto-linking: when you write a non-session note during an active session, the CLI auto-appends a wikilink to the session note via `[[note-name]]`
- Plan mirroring: plans created during a session are automatically mirrored as Decision notes
- Visual browsing in Obsidian with backlinks and Dataview queries

**Commands:**
```bash
agent-notes memory init                  # create folder structure and Index.md
agent-notes memory list                  # list all notes (by category or agent)
agent-notes memory vault                 # show storage, path, and init status
agent-notes memory index                 # regenerate Index.md
agent-notes memory add <title> <body> [type] [agent]  # type: pattern|decision|mistake|context|session
agent-notes memory show <agent>          # show one agent's notes
agent-notes memory reset [agent]         # clear memory (confirmation required)
agent-notes memory export                # back up to memory-backup/
agent-notes memory import                # restore from memory-backup/
agent-notes install --reconfigure        # switch storage
```

**Note format example:**
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

### Wiki (per-project knowledge brain)

Implements Karpathy's LLM Wiki pattern (v1). Auto-creates a folder per project (derived from current working directory name) with immutable source material and LLM-maintained wiki pages.

**Structure:**
```
<vault-root>/<project-name>/
├── raw/                # immutable source material
└── wiki/
    ├── sources/        # ingested source pages
    ├── concepts/       # domain concepts
    ├── entities/       # external tools/services
    ├── synthesis/      # cross-cutting themes
    ├── sessions/       # session logs
    ├── index.md
    └── log.md
```

**Key operations:**

- **Ingest** — Process source material (URLs, files, folders), extract key info, update entity/concept pages, append to log. Feeds external knowledge into the wiki brain for persistent, queryable knowledge.
  
  Use during Claude Code sessions: `/ingest https://docs.example.com/api` or `/ingest ./path/to/file.py`
  
  CLI fallback: `agent-notes memory ingest "<title>" "<body>" "<concepts>" "<entities>" "<tags>"`

- **Query** — Search wiki pages, synthesize answers with citations, optionally file answers back as new pages

- **Lint** — Health-check for contradictions, stale claims, orphan pages, missing cross-references

**Commands:**
```bash
agent-notes memory init                  # create folder structure and Index.md
agent-notes memory list                  # list all notes
agent-notes memory vault                 # show storage, path, and init status
agent-notes memory index                 # regenerate Index.md
agent-notes memory add <title> <body> [type]          # type: source|concept|entity|synthesis|session
agent-notes memory ingest <title> <body> <concepts> <entities> <tags>  # manual ingest
agent-notes memory query <question>      # search wiki pages
agent-notes memory lint                  # health-check
agent-notes memory reset                 # clear memory (confirmation required)
agent-notes memory export                # back up to memory-backup/
agent-notes memory import                # restore from memory-backup/
agent-notes install --reconfigure        # switch storage
```

### Project scoping (Obsidian + Wiki only)

Both Obsidian and Wiki storage modes auto-create a folder named after the current working directory, isolating different projects' memory.

**Example:**
- Working in `~/code/my-app/` → memory stored at `<vault>/my-app/`
- Working in `~/code/another-project/` → memory stored at `<vault>/another-project/`

The vault root is configured once during `agent-notes install`; the project path is resolved at runtime from the current working directory.

### Obsidian setup

Run `agent-notes install` and pick Obsidian when prompted. The wizard auto-detects existing vaults under `~/Documents`, `~/Desktop`, and `~`. To initialize the vault structure:

```bash
agent-notes memory init
```

The installed `CLAUDE.md` already points agents to your vault. At the start of a session Claude reads `Index.md`; at the end it can save insights with `agent-notes memory add`.

</details>

---

<details>
<summary>Skills</summary>

42+ on-demand knowledge modules across Rails, Docker, Kamal, Git, and Process. Run `agent-notes list skills` for the current list, or browse `agent_notes/data/skills/`.

The session context hook auto-generates a skill index from SKILL.md frontmatter at install time, so agents always know what skills are available without loading full skill content. This keeps context overhead low while maintaining skill discoverability.

### Using skills in Claude Code / OpenCode

```
Use the rails-models skill to help with this association
Load the docker-compose skill for multi-service setup
```

### Core skills addressing failure modes

| Failure mode | What goes wrong | Skills that help |
|---|---|---|
| Misalignment | Claude starts building before the problem is resolved | `/grill-me`, `/grill-with-docs` |
| Verbosity | Responses are bloated; context window fills with noise | `/caveman`, `/setup-project-context` |
| Broken code | Claude codes without a feedback loop or evidence trail | `/tdd` (improved), `/debugging-protocol` (improved) |
| Ball of mud | Architecture drifts; modules grow shallow and tangled | `/improve-codebase-architecture`, `/zoom-out` |

**Skill descriptions:**

- `/grill-me` — Interview the user until the problem is fully resolved before touching code
- `/grill-with-docs` — Same, but cross-references CONTEXT.md and ADRs and updates them inline
- `/caveman` — Ultra-compressed reply mode (~75% token savings) for rapid iteration
- `/setup-project-context` — Bootstraps a CONTEXT.md domain glossary (ubiquitous language)
- `/tdd` — RED-GREEN-REFACTOR with tracer-bullet vertical slices; horizontal-slicing anti-pattern added
- `/debugging-protocol` — Phase 1 rewritten as "build a feedback loop first" with 9 strategies
- `/improve-codebase-architecture` — Deletion test to find shallow modules; surfaces deepening opportunities
- `/zoom-out` — Quick orientation map of an unfamiliar code area

</details>

---

<details>
<summary>Configuration</summary>

### CLI Reference

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
| `memory [add\|init\|vault\|index\|ingest\|query\|lint\|list\|size\|show\|reset\|export\|import] [name]` | Manage agent memory |
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

# List agents, models, or skills
agent-notes list agents
agent-notes list models
agent-notes list skills

# Manage agent memory
agent-notes memory list
agent-notes memory add "Rails enum prefix" \
  "Always use _prefix: true to avoid method name collisions" \
  pattern coder

# Check API key configuration
agent-notes config provider openrouter   # prints "configured" or "no key"

# Reconfigure providers
agent-notes config providers

# Show installation status
agent-notes info

# Validate configuration files
agent-notes validate
```

### Role models

Configure which Claude model powers each role. The default uses Opus 4.6 for reasoning, Sonnet 4.6 for execution, Haiku 4.5 for exploration.

```bash
agent-notes set role lead claude-opus-4-20250514
agent-notes set role coder claude-sonnet-4-20250514
agent-notes set role explorer claude-haiku-4-5-20251001
```

### Providers

agent-notes supports multiple API providers for routing requests. Configure providers via:

```bash
agent-notes config providers     # interactive wizard
agent-notes config provider <name>      # check if configured (without exposing key)
```

</details>

---

<details>
<summary>Development</summary>

### Building and testing

Python 3.10+ required. Build from source and run tests:

```bash
python -m build && pipx install dist/*.whl
python3 -m pytest tests/ -q
```

### Development workflow

1. Edit source files in `agent_notes/data/` or Python modules
2. Run `python -m build` to rebuild the wheel
3. Run `pipx reinstall dist/*.whl` to install the updated version
4. Run `agent-notes validate` to lint configuration files
5. Run tests: `python3 -m pytest tests/ -q`

### Test structure

- `tests/functional/` — Unit tests
- `tests/integration/` — Build output and artifact validation
- `tests/plugins/` — Plugin artifact validation

### Contributing guidelines

When adding new content:

1. **Edit source files** — all changes go in `agent_notes/data/` directory
2. **Run build** — `python -m build` to generate platform configs
3. **Run tests** — `python3 -m pytest tests/ -q` before committing
4. **Validate** — `agent-notes validate` before committing
5. **Keep it generic** — remove app-specific references
6. **Show examples** — include code samples with explanations
7. **Stay modular** — each skill should be independently usable
8. **Stay concise** — agent prompts under 60 lines

### Architecture

agent-notes is a 4-layer engine (domain / registries / services / commands). All extensible content (CLIs, models, roles, agents, skills, rules) lives in `agent_notes/data/` as YAML — adding a new CLI/model/role is a YAML drop, no Python changes. Context is loaded in tiers: always-loaded (CLAUDE.md, rules, skill catalog), lazy-loaded (full skill content, agent prompts), and pull-based (memory notes).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ADD_CLI.md](docs/ADD_CLI.md), [docs/ADD_MODEL.md](docs/ADD_MODEL.md), [docs/ADD_ROLE.md](docs/ADD_ROLE.md).

</details>

---

## Inspired by

- [Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — The wiki memory backend implements his compile-once, query-forever knowledge pattern with structured page types and three core operations (ingest, query, lint)
- [Matt Pocock's skills repo](https://github.com/mattpocock/skills) — Skill format (SKILL.md per directory), failure-mode table (misalignment, verbosity, broken code, architectural degradation), and several core skills (tdd, grill-me, grill-with-docs, improve-codebase-architecture, zoom-out, caveman)

## License

MIT
