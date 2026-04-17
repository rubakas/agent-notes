# agent-notes

AI agent configuration manager for Claude Code, OpenCode, and GitHub Copilot.

## Quick Start

```bash
git clone https://github.com/rubakas/agent-notes.git ~/agent-notes
ln -sf ~/agent-notes/bin/agent-notes /usr/local/bin/agent-notes
agent-notes install
agent-notes doctor
```

Update anytime with `cd ~/agent-notes && git pull && agent-notes update`.

## What's Included

| Component | Description |
|-----------|-------------|
| **Skills** | On-demand knowledge modules (Rails, Docker, etc.) |
| **Agents** | Specialized AI subagents with hierarchical model strategy |
| **Rules** | Global instructions, code quality, safety, and Copilot config |

## CLI Reference

```
agent-notes <command> [options]
```

| Command | Description |
|---------|-------------|
| `install [--local] [--copy]` | Build and install components |
| `uninstall [--local]` | Remove installed components |
| `update` | Pull latest, rebuild, reinstall |
| `doctor [--local] [--fix]` | Check installation health |
| `info` | Show status and component counts |
| `list [agents\|skills\|rules\|all]` | List installed components |
| `validate` | Lint source configuration files |
| `memory [list\|size\|show\|reset\|export\|import] [name]` | Manage agent memory |

### Examples

```bash
# Global install (all projects)
agent-notes install

# Local install (current project only)
agent-notes install --local

# Copy files instead of symlink (for customization)
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

## Architecture

**Single source of truth:** `source/` → `build` → `dist/` → `install`

1. **Source** — YAML metadata + Markdown prompts
2. **Build** — Generate platform-specific configs
3. **Dist** — Built artifacts ready for installation  
4. **Install** — Deploy via symlinks or copy

## Project Structure

```
agent-notes/
├── bin/agent-notes          # CLI wrapper (entry point)
├── lib/agent_notes/         # Python implementation
├── source/                  # Single source of truth
│   ├── agents.yaml          # Agent metadata
│   ├── agents/              # Agent prompt files
│   ├── global.md            # Global instructions
│   └── rules/               # Code quality rules
├── dist/                    # Built artifacts
│   ├── cli/                 # Agent configs by platform
│   ├── rules/               # Rule files
│   └── skills/              # Skill directories
├── scripts/                 # Build/utility scripts
├── tests/                   # Test suite
└── <skill-dirs>/            # Individual skill directories
```

## Install Methods

### Git clone + wrapper (recommended)

```bash
git clone https://github.com/rubakas/agent-notes.git ~/agent-notes
ln -sf ~/agent-notes/bin/agent-notes /usr/local/bin/agent-notes
agent-notes install
```

### Pip install (future)

```bash
pip install agent-notes
agent-notes install
```

### Homebrew (future)

```bash
brew install rubakas/tap/agent-notes
agent-notes install
```

## Project-Level Overrides

Use `--local --copy` for project-specific customizations:

```bash
agent-notes install --local --copy
```

Then edit the copied files in `.claude/` or `.opencode/` directories.

**Precedence:** Project-level configs replace global versions entirely.

## Skills

On-demand knowledge modules loaded mid-conversation.

### Available skills

**Rails:**
`commit`, `rails-models`, `rails-controllers`, `rails-routes`, `rails-concerns`, `rails-views`, `rails-views-advanced`, `rails-view-components`, `rails-view-components-advanced`, `rails-helpers`, `rails-javascript`, `rails-jobs`, `rails-mailers`, `rails-broadcasting`, `rails-migrations`, `rails-active-storage`, `rails-validations`, `rails-testing-controllers`, `rails-testing-models`, `rails-testing-system`, `rails-style`, `rails-controllers-advanced`, `rails-models-advanced`, `rails-initializers`, `rails-lib`, `rails-kamal`

**Docker:**
`docker-dockerfile`, `docker-dockerfile-languages`, `docker-compose`, `docker-compose-advanced`

**Utility:**
`commit` — generates conventional commit messages from staged changes and branch name

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
PYTHONPATH=lib pytest tests/
```

### Building

```bash
PYTHONPATH=lib python3 -m agent_notes build
```

### Validating

```bash
PYTHONPATH=lib python3 -m agent_notes validate
```

### Project layout

- `source/` — single source of truth (edit here)
- `dist/` — generated output (do not edit)
- `lib/agent_notes/` — CLI implementation
- `tests/` — test suite
- `scripts/` — dev-only tools (release, etc.)

## Contributing

When adding new content:

1. **Edit source files** — all changes go in `source/` directory
2. **Run build** — `agent-notes build` to generate platform configs
3. **Validate** — `agent-notes validate` before committing
4. **Keep it generic** — remove app-specific references
5. **Show examples** — include code samples with explanations
6. **Stay modular** — each skill should be independently usable
7. **Stay concise** — agent prompts under 60 lines

## License

MIT