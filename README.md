# AI Agent Notes

Modular skills, agents, and rules for AI coding assistants. Clone once, install globally or per-project, use everywhere.

Works with **Claude Code** and **OpenCode**. Skills also work with any tool that reads `SKILL.md` files.

## Quick Start

```bash
git clone git@github.com:rubakas/agent-notes.git ~/agent-notes
bash ~/agent-notes/scripts/agent-notes install all global
```

Optionally make the CLI available system-wide:

```bash
ln -sf ~/agent-notes/scripts/agent-notes /usr/local/bin/agent-notes
```

Then use from anywhere:

```bash
agent-notes install all global
agent-notes info
agent-notes check
```

Update anytime with `cd ~/agent-notes && git pull` — symlinks keep everything in sync.

## What's Included

Run `agent-notes info` to see current counts and status.

| Component | Description |
|-----------|-------------|
| **Skills** | On-demand knowledge modules (Rails, Docker, etc.) |
| **Agents** | Specialized AI subagents with hierarchical model strategy |
| **Rules** | Global instructions, code quality, safety, and Copilot config |

## CLI Reference

```
agent-notes <command> [args...]
```

| Command | Description |
|---------|-------------|
| `install <what> <where> [--copy]` | Install components |
| `uninstall <what> <where>` | Remove installed components |
| `validate` | Lint all configs in the repo |
| `memory [opts]` | Manage agent memory |
| `check` | Validate existing symlinks |
| `info` | Show component counts and status |
| `help` | Show usage |

**Install/uninstall arguments:**

| Arg | Values |
|-----|--------|
| `<what>` | `all` \| `skills` \| `agents` \| `rules` |
| `<where>` | `global` \| `local` |
| `--copy` | Copy files instead of symlink (local only) |

## Install

### Global (applies to all projects)

```bash
agent-notes install all global       # everything
agent-notes install skills global    # skills only
agent-notes install agents global    # agents only
agent-notes install rules global     # rules only
```

### Local (current project only)

```bash
# Symlink — stays in sync with agent-notes repo
agent-notes install all local

# Copy — standalone, editable, independent
agent-notes install all local --copy
```

Use `--copy` when you want to customize configs for a specific project. Use symlinks for projects that follow your standard setup.

### Where things go

**Global install:**

| Source | Claude Code | OpenCode | Other |
|--------|------------|----------|-------|
| Skills | `~/.claude/skills/` | `~/.config/opencode/skills/` | `~/.agents/skills/` |
| Agents | `~/.claude/agents/` | `~/.config/opencode/agents/` | — |
| Rules | `~/.claude/CLAUDE.md`, `~/.claude/rules/` | `~/.config/opencode/AGENTS.md` | `~/.github/copilot-instructions.md` |

**Local install:**

| Source | Claude Code | OpenCode |
|--------|------------|----------|
| Skills | `.claude/skills/` | `.opencode/skills/` |
| Agents | `.claude/agents/` | `.opencode/agents/` |
| Rules | `CLAUDE.md`, `.claude/rules/` | `AGENTS.md` |

## Uninstall

```bash
agent-notes uninstall all global      # remove all global installs
agent-notes uninstall agents global   # remove only agents
agent-notes uninstall all local       # remove project-level installs
```

Only removes symlinks. Copied files (from `--copy`) are reported but not deleted.

## Management

### Check installation health

```bash
agent-notes check
```

Reports `OK`, `MISSING`, `BROKEN`, or `SHADOWED` for every expected symlink.

### Validate configs

```bash
agent-notes validate
```

Lints all agent and skill files: frontmatter, naming, line counts, duplicates. Also runs in CI on every push via GitHub Actions.

### Manage agent memory

```bash
agent-notes memory                    # list all memories
agent-notes memory --size             # disk usage
agent-notes memory --show coder       # view one agent's memory
agent-notes memory --reset reviewer   # clear one agent
agent-notes memory --reset            # clear all
agent-notes memory --export           # backup to repo
agent-notes memory --import           # restore from backup
```

## Agents

Specialized subagents with a hierarchical model strategy: **Opus decides, Sonnet executes, Haiku explores.**

### Why agents instead of a single Opus session?

A single Opus session works fine for simple tasks. The agent architecture saves tokens and improves quality on complex work:

- **Opus lead** only plans and reviews (small context). Workers run in isolated windows.
- **Sonnet workers** cost ~5x less than Opus for focused implementation tasks.
- **Haiku explorer** costs ~60x less than Opus for quick lookups.
- **Parallel execution**: independent subtasks run simultaneously.
- **Isolated context**: each agent sees only what it needs, reducing noise.

Use agents for multi-step work. Use a single session for quick edits and questions.

### Agent roster

| Agent | Model | Role |
|-------|-------|------|
| **lead** | Opus 4 | Plans, delegates, reviews. The only Opus agent. |
| **coder** | Sonnet 4 | Implements features, fixes bugs, edits files. |
| **reviewer** | Sonnet 4 | Code quality review. Read-only. |
| **security-auditor** | Sonnet 4 | Security vulnerability analysis. Read-only. |
| **spec-writer** | Sonnet 4 | Writes tests for any framework. |
| **spec-runner** | Sonnet 4 | Diagnoses and fixes failing tests. |
| **system-auditor** | Sonnet 4 | Codebase health: duplication, N+1, coupling. Read-only. |
| **database-specialist** | Sonnet 4 | Schema design, indexes, query performance, migrations. Read-only. |
| **performance-profiler** | Sonnet 4 | Response times, memory, caching, bundle size. Read-only. |
| **api-reviewer** | Sonnet 4 | API design, versioning, error handling, backward compatibility. Read-only. |
| **tech-writer** | Sonnet 4 | Documentation: READMEs, API docs, changelogs. |
| **devops** | Sonnet 4 | Docker, CI/CD, deployment configs. |
| **explorer** | Haiku 4.5 | Fast file discovery and pattern search. Read-only. |

### Format differences

Each agent exists in two formats with the same body content but different frontmatter:

| Feature | Claude Code (`agents/`) | OpenCode (`agents-opencode/`) |
|---------|------------------------|-------------------------------|
| Model ID | Shorthand (`opus`, `sonnet`, `haiku`) | Full ID (`github-copilot/claude-sonnet-4`) |
| Mode | `role` (implicit) | `mode: primary` or `mode: subagent` |
| Read-only | `disallowedTools: Write, Edit` | `permission: { edit: deny }` |
| Bash restrict | `disallowedTools: Bash` | `permission: { bash: { "*": deny, "grep *": allow } }` |
| Effort | `effort: medium` | Not supported |
| Memory | `memory: user` | Not supported |
| Color | `color: yellow` | Not supported |

### How the team works

```
You (human)
  |
  +-- Simple task ------> Main session (direct work)
  |
  +-- Complex task -----> Lead (Opus)
                           +-- Explorer (Haiku)     quick lookups
                           +-- Coder (Sonnet)       implementation
                           +-- Reviewer (Sonnet)    code review
                           +-- Spec Writer (Sonnet) tests
                           +-- Spec Runner (Sonnet) fix tests
                           +-- Security (Sonnet)    security audit
                           +-- Auditor (Sonnet)     codebase health
                           +-- DB Specialist (Sonnet) schema & queries
                           +-- Perf Profiler (Sonnet) performance
                           +-- API Reviewer (Sonnet)  API design
                           +-- Tech Writer (Sonnet) documentation
                           +-- DevOps (Sonnet)      infrastructure
```

### Usage

**Claude Code:**
```bash
claude --agent lead                              # start with lead orchestrator
```
```
Use the reviewer agent to review my recent changes
@"coder (agent)" implement the search feature
```

**OpenCode:**
```
@lead plan the implementation of the auth module
@reviewer check src/api/ for issues
```

### Token efficiency

Based on [Claude's prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct):

- **Concise prompts**: each agent file is under 50 lines. Only adds context Claude doesn't already know.
- **No over-prompting**: neutral language avoids overtriggering in Claude 4.x models.
- **Effort levels** (Claude Code only): Opus `high`, Sonnet `medium`, Haiku `low` — per Claude docs.
- **Anti-spawning rules**: the lead defines when NOT to spawn agents to prevent unnecessary overhead.
- **User-level memory** (Claude Code only): agents accumulate learnings across sessions without consuming prompt tokens.

## Skills

On-demand knowledge modules loaded mid-conversation.

### Available skills

**Rails:**
`/rails-models`, `/rails-controllers`, `/rails-routes`, `/rails-concerns`,
`/rails-views`, `/rails-views-advanced`, `/rails-view-components`,
`/rails-view-components-advanced`, `/rails-helpers`, `/rails-javascript`,
`/rails-jobs`, `/rails-mailers`, `/rails-broadcasting`, `/rails-migrations`,
`/rails-active-storage`, `/rails-validations`, `/rails-testing-controllers`,
`/rails-testing-models`, `/rails-testing-system`, `/rails-style`,
`/rails-controllers-advanced`, `/rails-models-advanced`, `/rails-initializers`,
`/rails-lib`, `/rails-kamal`

**Docker:**
`/docker-dockerfile`, `/docker-dockerfile-languages`, `/docker-compose`, `/docker-compose-advanced`

**Utility:**
`/commit` — generates conventional commit messages from staged changes and branch name

### Passive include (alternative)

Instead of skills, you can include patterns directly in your project instructions file:

```markdown
# In your project's CLAUDE.md or AGENTS.md
@agent-notes/rails/index.md
@agent-notes/docker/index.md
```

## Project-Level Overrides

When you need project-specific customizations, use `--local --copy` to get standalone editable files:

```bash
# Copy agents and rules into your project
agent-notes install agents local --copy
agent-notes install rules local --copy
```

Then edit the copies for your project:

**Claude Code** — `.claude/agents/reviewer.md`:
```markdown
---
name: reviewer
description: Reviews code for this Rails 8 financial app.
model: sonnet
disallowedTools: Write, Edit
memory: user
color: yellow
---

(global reviewer rules here, plus:)

## Project-specific rules

- Money-rails for all monetary values. Never Float, always decimal(19,4).
- Pundit authorization required on every controller action.
- All financial data access must have audit trail.
```

**OpenCode** — `.opencode/agents/reviewer.md`:
```markdown
---
description: Reviews code for this Rails 8 financial app.
mode: subagent
model: anthropic/claude-sonnet-4-20250514
permission:
  edit: deny
---

(same body with project-specific additions)
```

**Precedence**: Project-level agents with the same name **replace** the global version entirely. Project-level rules (CLAUDE.md, AGENTS.md) **extend** global rules.

## Repository Structure

```
agent-notes/
+-- agents/                          # Claude Code agent definitions
+-- agents-opencode/                 # OpenCode agent definitions
+-- global/                          # Global config files
|   +-- CLAUDE.md                    #   Claude Code instructions
|   +-- AGENTS.md                    #   OpenCode instructions
|   +-- rules/                       #   Code quality + safety rules
|   +-- copilot-instructions.md      #   GitHub Copilot config
+-- rails/                           # Rails passive-include modules
+-- docker/                          # Docker passive-include modules
+-- rails-*/                         # Rails skill directories
+-- docker-*/                        # Docker skill directories
+-- commit/                          # Commit message skill
+-- scripts/
|   +-- agent-notes                  # CLI wrapper (entry point)
|   +-- install.sh                   # Install components
|   +-- uninstall.sh                 # Remove components
|   +-- validate.sh                  # Lint all configs
|   +-- memory.sh                    # Agent memory management
+-- .github/workflows/
|   +-- validate.yml                 # CI validation
+-- README.md
```

## Contributing

When adding new content:

1. **Keep it generic** — remove app-specific references
2. **Show examples** — include code samples with explanations
3. **Explain why** — document the reasoning behind patterns
4. **Stay modular** — each file should be independently usable
5. **Stay concise** — agent prompts under 60 lines, skills focused on one topic
6. **Run validation** — `agent-notes validate` before committing

## License

MIT
