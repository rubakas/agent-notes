# AI Agent Notes

Modular configuration files and best practices for AI coding agents across different technologies and frameworks.

## Purpose

AI coding agents work best when they have clear, structured context about your codebase. This repository provides reusable, modular patterns that you can include in your projects to give AI assistants comprehensive knowledge of your tech stack's best practices.

**Key Benefits:**
- 📦 **Modular** - Include only what you need
- 🔄 **Reusable** - Copy across all your projects
- 🎯 **Focused** - One file per technology stack
- ✅ **Production-Ready** - Extracted from real codebases
- 📚 **Comprehensive** - Covers all major components

Instead of explaining patterns repeatedly in every conversation, include these once in your project's `AGENTS.md` (OpenCode) or `CLAUDE.md` (Claude Code), and AI assistants will automatically understand your conventions.

## Available Patterns

| Technology | Status | Modules | Quick Start |
|------------|--------|---------|-------------|
| **Rails** | ✅ Complete | 19 modules | `@agent-notes/rails/index.md` |
| **Docker** | ✅ Complete | 2 modules | `@agent-notes/docker/index.md` |
| **React** | 🚧 Planned | - | Coming soon |
| **Next.js** | 🚧 Planned | - | Coming soon |
| **Vue** | 🚧 Planned | - | Coming soon |
| **Shell Scripts** | 🚧 Planned | - | Coming soon |

### Rails (✅ Complete - 19 Modules)

Comprehensive Rails patterns and best practices extracted from production codebases.

**Quick Start:**
```markdown
# In your project's AGENTS.md or CLAUDE.md
@agent-notes/rails/index.md
```

**Includes:**
- **Core:** Models, Controllers, Routes, Concerns, Tests
- **Frontend:** Views, ViewComponents, Helpers, JavaScript (Stimulus/Turbo)
- **Background:** Jobs, Mailers, Broadcasting
- **Data:** Migrations, Active Storage, Validations
- **Infrastructure:** Lib, Initializers, Kamal (Deployment)
- **Code Style & Conventions**

**Documentation:** [rails/README.md](rails/README.md)

### Docker (✅ Complete - 2 Modules)

Production-ready Docker and Docker Compose patterns based on official Docker documentation.

**Quick Start:**
```markdown
# In your project's AGENTS.md or CLAUDE.md
@agent-notes/docker/index.md
```

**Includes:**
- **Dockerfile Patterns:** Multi-stage builds, security (non-root UID > 10,000), health checks, layer optimization
- **Docker Compose:** Service orchestration, health checks, dependencies, dev/prod configs
- **Security:** Official Docker security best practices, vulnerability scanning
- **Languages:** Node.js, Python, Ruby/Rails, Go patterns

**Documentation:** [docker/README.md](docker/README.md)

## Getting Started

There are two ways to use agent-notes. Pick one or use both.

### Option A: Global Skills (recommended)

Skills are loaded **on-demand** mid-conversation (e.g. type `/rails-models`).
They work across all your projects — install once, use everywhere.

**Step 1.** Clone the repo anywhere:
```bash
git clone git@github.com:rubakas/agent-notes.git ~/agent-notes
```

**Step 2.** Run the install script:
```bash
bash ~/agent-notes/scripts/install-skills.sh
```

This symlinks all 29 skills into:
- `~/.claude/skills/` (Claude Code)
- `~/.config/opencode/skills/` (OpenCode)
- `~/.agents/skills/` (universal)

To install for a specific tool only:
```bash
bash ~/agent-notes/scripts/install-skills.sh --opencode   # OpenCode only
bash ~/agent-notes/scripts/install-skills.sh --claude      # Claude Code only
```

**Step 3.** Use skills in any project:
```
/rails-models
/docker-compose
/rails-testing-controllers
```

Updates are automatic — just `git pull` in the cloned repo.

### Option B: Passive Include in Your Project

Patterns are loaded **automatically** every session via your project's instructions file.
Good when your whole team should always have the context.

**Step 1.** Clone the repo inside your project:
```bash
cd /path/to/your/project
git clone git@github.com:rubakas/agent-notes.git
```

**Step 2.** Reference the patterns in your instructions file:

**OpenCode** — create or edit `AGENTS.md`:
```markdown
# My Project

@agent-notes/rails/index.md
@agent-notes/docker/index.md
```

Or use `opencode.json` instead:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "agent-notes/rails/index.md",
    "agent-notes/docker/index.md"
  ]
}
```

**Claude Code** — create or edit `CLAUDE.md`:
```markdown
# My Project

@agent-notes/rails/index.md
@agent-notes/docker/index.md
```

**Step 3 (optional).** Include only specific modules:
```markdown
@agent-notes/rails/models.md
@agent-notes/rails/controllers.md
@agent-notes/rails/style.md
```

### Which approach to use?

| | Global Skills (A) | Passive Include (B) |
|---|---|---|
| **Scope** | All projects | Single project |
| **Loading** | On-demand (`/rails-models`) | Always loaded every session |
| **Setup** | Once, globally | Per project |
| **Team sharing** | Each dev installs | Commit AGENTS.md / CLAUDE.md to git |
| **Best for** | Personal reference | Team-wide conventions |

You can use both — install skills globally AND include patterns in a project.

### Available skills

`/rails-models`, `/rails-controllers`, `/rails-routes`, `/rails-concerns`,
`/rails-views`, `/rails-views-advanced`, `/rails-view-components`,
`/rails-view-components-advanced`, `/rails-helpers`, `/rails-javascript`,
`/rails-jobs`, `/rails-mailers`, `/rails-broadcasting`, `/rails-migrations`,
`/rails-active-storage`, `/rails-validations`, `/rails-testing-controllers`,
`/rails-testing-models`, `/rails-testing-system`, `/rails-style`,
`/rails-controllers-advanced`, `/rails-models-advanced`, `/rails-initializers`,
`/rails-lib`, `/rails-kamal`, `/docker-dockerfile`, `/docker-dockerfile-languages`,
`/docker-compose`, `/docker-compose-advanced`

## Repository Structure

```
agent-notes/
├── rails/                # Rails patterns (19 modules)
│   ├── index.md          # Entry point — includes all modules
│   ├── models.md
│   ├── controllers.md
│   ├── views.md
│   └── ...
├── docker/               # Docker patterns (2 modules)
│   ├── index.md          # Entry point — includes all modules
│   ├── dockerfile.md
│   └── compose.md
├── rails-models/         # Skill directories (29 total)
│   └── SKILL.md          #   Works with OpenCode + Claude Code
├── scripts/
│   └── install-skills.sh # Global skill installer
└── README.md
```

**Each technology folder has an entry point:**
- `rails/index.md` — All 19 Rails modules
- `docker/index.md` — All 2 Docker modules

## Contributing

These patterns are extracted from real production codebases and represent battle-tested practices. When adding new content:

1. **Keep it generic** - Remove app-specific references
2. **Show examples** - Include code samples with explanations
3. **Explain why** - Document the reasoning behind patterns
4. **Include testing** - Show how to test the patterns
5. **Stay modular** - Each file should be independently usable

## Philosophy

- **Modular** - Include only what you need
- **Generic** - Patterns work across projects
- **Production-Ready** - Extracted from real applications
- **Well-Documented** - Clear examples and explanations
- **AI-Optimized** - Structured for AI agent comprehension

## License

MIT
