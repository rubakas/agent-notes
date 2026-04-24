# agent-notes

AI agent configuration manager for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [OpenCode](https://github.com/opencode-ai/opencode).

Configures a Lead agent (Opus) that orchestrates a team of 18 specialized subagents across three model tiers — so Opus plans, Sonnet executes, and Haiku explores.

## Quick Start

```bash
git clone https://github.com/rubakas/agent-notes.git ~/agent-notes
ln -sf ~/agent-notes/bin/agent-notes /usr/local/bin/agent-notes
agent-notes install    # interactive wizard guides you through setup
agent-notes doctor
```

Update anytime with `cd ~/agent-notes && git pull && agent-notes update`.

## What's Included

| Component | Description |
|-----------|-------------|
| **Skills** | 31 on-demand knowledge modules (Rails, Docker, Git, Kamal) |
| **Agents** | 18 specialized AI subagents with hierarchical model strategy |
| **Rules** | Global instructions, code quality, and safety guardrails |
| **Config** | Global instructions for Claude Code, OpenCode, and GitHub Copilot |

## CLI Reference

```
agent-notes <command> [options]
```

| Command | Description |
|---------|-------------|
| `install [--local] [--copy]` | Interactive wizard or direct install |
| `uninstall [--local]` | Remove installed components |
| `update` | Pull latest, rebuild, reinstall |
| `doctor [--local] [--fix]` | Check installation health |
| `info` | Show status and component counts |
| `list [clis\|models\|roles\|agents\|skills\|rules\|all]` | List engine components or installed |
| `set role <role> <model> [--cli <cli>]` | Change model for a role (Phase 10+) |
| `regenerate [--cli <cli>]` | Rebuild files from state.json (Phase 10+) |
| `validate` | Lint source configuration files |
| `memory [list\|size\|show\|reset\|export\|import] [name]` | Manage agent memory |

### Supported platforms

| Platform | Install target | Config format |
|----------|---------------|---------------|
| **Claude Code** | `~/.claude/` | YAML frontmatter + Markdown prompts |
| **OpenCode** | `~/.config/opencode/` | YAML frontmatter + Markdown prompts |
| **GitHub Copilot** | `~/.github/` | `copilot-instructions.md` |

### Examples

```bash
# Interactive install (recommended)
agent-notes install

# Example wizard session:
#
#   Which CLI do you use?
#     1) [*] Claude Code
#     2) [*] OpenCode
#   Enter numbers to toggle (comma-separated), or press enter for defaults.
#   Choice:                          ← press enter to keep both
#
#   Where to install?
#     1) * Global (~/.claude, ~/.config/opencode)
#     2)   Local (current project)
#   Choice [1]:                      ← press enter for global
#
#   How to install?
#     1) * Symlink (auto-updates when source changes)
#     2)   Copy (standalone, allows local customization)
#   Choice [1]:                      ← press enter for symlink
#
#   Which skills to include?
#     1) [*] Rails — models, controllers, views, routes, testing (22 skills)
#     2) [*] Docker — Dockerfile, Compose patterns (4 skills)
#     3) [*] Kamal — deployment with Kamal (1 skill)
#     4) [*] Git — commit workflow, conventional commits (1 skill)
#   Choice:                          ← press enter for all
#
#   Ready to install:
#     CLI:      Claude Code + OpenCode
#     Scope:    Global (~/.claude, ~/.config/opencode)
#     Mode:     Symlink
#     Skills:   Rails (22), Docker (4), Kamal (1), Git (1)
#     Agents:   18 (Claude Code) + 19 (OpenCode)
#     Config:   CLAUDE.md, AGENTS.md
#     Rules:    2
#   Proceed? [Y/n]: Y

# Direct install (scripted, no wizard)
agent-notes install --local
agent-notes install --local --copy

# Check health and fix issues
agent-notes doctor --fix

# Manage agent memory
agent-notes memory list
agent-notes memory show coder
agent-notes memory reset reviewer
```

## Agent Team

Specialized subagents with hierarchical model strategy: **Opus 4.7 decides, Sonnet 4 executes, Haiku 4.5 explores.**

### Agent roster

| Agent | Model | Role |
|-------|-------|------|
| **lead** | Opus 4.7 | Plans, delegates, reviews. The only Opus agent. |
| **coder** | Sonnet 4 | Implements features, fixes bugs, edits files. |
| **reviewer** | Sonnet 4 | Code quality review. Read-only. |
| **security-auditor** | Sonnet 4 | Security vulnerability analysis. Read-only. |
| **test-writer** | Sonnet 4 | Writes tests for any framework. |
| **test-runner** | Sonnet 4 | Diagnoses and fixes failing tests. |
| **system-auditor** | Sonnet 4 | Codebase health: duplication, N+1, coupling. Read-only. |
| **database-specialist** | Sonnet 4 | Schema design, indexes, query performance, migrations. Read-only. |
| **performance-profiler** | Sonnet 4 | Response times, memory, caching, bundle size. Read-only. |
| **api-reviewer** | Haiku 4.5 | API design, versioning, error handling, backward compatibility. Read-only. |
| **tech-writer** | Haiku 4.5 | Documentation: READMEs, API docs, changelogs. |
| **devops** | Sonnet 4 | Docker, CI/CD, deployment configs. |
| **explorer** | Haiku 4.5 | Fast file discovery and pattern search. Read-only. |

### 4-phase lead workflow

```
1. ANALYZE — Lead reviews requirements, explores codebase
2. EXECUTE — Delegates to specialized agents (parallel execution)
3. REVIEW — Quality check by reviewer agents
4. VERIFY — Final validation and integration
```

### Team diagram

```
You (human)
  |
  +-- Simple task ------> Main session (direct work)
  |
  +-- Complex task -----> Lead (Opus 4.7)
                           +-- Explorer (Haiku 4.5)     quick lookups
                           +-- Coder (Sonnet 4)         implementation
                           +-- Reviewer (Sonnet 4)      code review
                            +-- Test Writer (Sonnet 4)   tests
                            +-- Test Runner (Sonnet 4)   fix tests
                           +-- Security (Sonnet 4)      security audit
                           +-- Auditor (Sonnet 4)       codebase health
                           +-- DB Specialist (Sonnet 4) schema & queries
                           +-- Perf Profiler (Sonnet 4) performance
                           +-- API Reviewer (Haiku 4.5) API design
                           +-- Tech Writer (Haiku 4.5)  documentation
                           +-- DevOps (Sonnet 4)        infrastructure
```

## Architecture: YAML-Driven Extensibility

Agent-notes is a **4-layer bounded-context engine** (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details):

| Layer | Purpose | Example |
|-------|---------|---------|
| **Domain** | Pure dataclasses (Agent, Model, Role, State) | `agent_notes/domain/` |
| **Registries** | YAML loaders from `data/` → domain types | `agent_notes/registries/` |
| **Services** | Technical concerns (I/O, rendering, state, install) | `agent_notes/services/` |
| **Commands** | CLI orchestrators (install, doctor, list, etc.) | `agent_notes/commands/` |

**Single source of truth:** `agent_notes/data/` holds all extensible content (CLI, model, role, agent, skill, rule YAMLs).

**Zero Python changes to add:**
- New CLI: drop `data/cli/cursor.yaml` 
- New model: drop `data/models/gpt-5.yaml`
- New role: drop `data/roles/specialist.yaml`

See [docs/ADD_CLI.md](docs/ADD_CLI.md), [docs/ADD_MODEL.md](docs/ADD_MODEL.md), [docs/ADD_ROLE.md](docs/ADD_ROLE.md) for guides.



## Project Structure

```
agent-notes/
├── bin/agent-notes          # CLI wrapper (entry point)
├── docs/
│   ├── ADD_CLI.md           # Guide: add a new CLI backend
│   ├── ADD_MODEL.md         # Guide: add a new AI model
│   ├── ADD_ROLE.md          # Guide: add a new agent role
│   ├── CLI_CAPABILITIES.md  # Source of truth for per-CLI features
│   └── ENGINE_PLAN.md       # Refactor phases and design details
├── agent_notes/             # Python implementation
│   ├── __init__.py, cli.py  # Core modules
│   ├── VERSION              # Package version
│   ├── data/                # Single source of truth
│   │   ├── cli/             # CLI descriptors
│   │   │   ├── claude.yaml, opencode.yaml, copilot.yaml
│   │   │   └── cursor.yaml  # (add your own)
│   │   ├── models/          # Model descriptors
│   │   │   ├── claude-opus-4-7.yaml, claude-sonnet-4.yaml, ...
│   │   │   └── kimi-k2.yaml # (add your own)
│   │   ├── roles/           # Role descriptors
│   │   │   ├── orchestrator.yaml, worker.yaml, scout.yaml, reasoner.yaml
│   │   │   └── specialist.yaml # (add your own)
│   │   ├── templates/frontmatter/
│   │   │   ├── claude.py, opencode.py
│   │   │   └── cursor.py    # (add if format differs from Claude/OpenCode)
│   │   ├── agents/
│   │   │   ├── agents.yaml  # Agent metadata + role declarations
│   │   │   └── *.md         # Agent prompt files
│   │   ├── skills/          # Skill directories
│   │   ├── rules/           # Code quality rules
│   │   ├── globals/         # Global config templates
│   │   └── commands/, scripts/
│   └── dist/                # Built artifacts (auto-generated, do not edit)
│       ├── claude/, opencode/
│       ├── rules/
│       └── skills/
├── scripts/                 # Build/utility scripts
└── tests/                   # Test suite
```

## Install Methods

### Git clone + wrapper (recommended)

```bash
git clone https://github.com/rubakas/agent-notes.git ~/agent-notes
ln -sf ~/agent-notes/bin/agent-notes /usr/local/bin/agent-notes
agent-notes install
```

After cloning, `agent-notes install` launches the interactive wizard to configure your setup.

### Pip install (future)

```bash
pip install agent-notes
agent-notes install
```

## Project-Level Overrides

Use `--local --copy` for project-specific customizations. The wizard handles local installs too, while `--local --copy` is for scripted/CI use:

```bash
agent-notes install --local --copy
```

Then edit the copied files in `.claude/` or `.opencode/` directories.

**Precedence:** Project-level configs replace global versions entirely.

## Skills

On-demand knowledge modules loaded mid-conversation.

### Available skills

**Rails:**
`rails-models`, `rails-controllers`, `rails-routes`, `rails-concerns`, `rails-views`, `rails-views-advanced`, `rails-view-components`, `rails-view-components-advanced`, `rails-helpers`, `rails-javascript`, `rails-jobs`, `rails-mailers`, `rails-broadcasting`, `rails-migrations`, `rails-active-storage`, `rails-validations`, `rails-testing-controllers`, `rails-testing-models`, `rails-testing-system`, `rails-style`, `rails-controllers-advanced`, `rails-models-advanced`, `rails-initializers`, `rails-lib`

**Docker:**
`docker-dockerfile`, `docker-dockerfile-languages`, `docker-compose`, `docker-compose-advanced`

**Kamal:**
`rails-kamal`

**Git:**
`git` — git workflow, commit chunking, conventional commit messages

### Usage

**Claude Code / OpenCode:**
```
Use the rails-models skill to help with this association
Load the docker-compose skill for multi-service setup
```

## Development

### Prerequisites

- Python 3.9+
- PyYAML (`pip install pyyaml`)

### Running tests

```bash
python3 -m pytest tests/
```

### Building

```bash
python3 -m agent_notes build
```

### Validating

```bash
python3 -m agent_notes validate
```

### Project layout

- `agent_notes/data/` — single source of truth (edit here)
- `agent_notes/dist/` — generated output (do not edit)
- `agent_notes/` — CLI implementation
- `tests/` — test suite
- `scripts/` — dev-only tools (release, etc.)

## Contributing

When adding new content:

1. **Edit source files** — all changes go in `agent_notes/data/` directory
2. **Run build** — `agent-notes build` to generate platform configs
3. **Validate** — `agent-notes validate` before committing
4. **Keep it generic** — remove app-specific references
5. **Show examples** — include code samples with explanations
6. **Stay modular** — each skill should be independently usable
7. **Stay concise** — agent prompts under 60 lines

## License

MIT