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

Instead of explaining patterns repeatedly in every conversation, include these once in your project's `CLAUDE.md`, and AI assistants will automatically understand your conventions.

## Available Patterns

| Technology | Status | Modules | Quick Start |
|------------|--------|---------|-------------|
| **Rails** | ✅ Complete | 17 modules | `@agent-notes/rails/index.md` |
| **Docker** | ✅ Complete | 2 modules | `@agent-notes/docker/index.md` |
| **React** | 🚧 Planned | - | Coming soon |
| **Next.js** | 🚧 Planned | - | Coming soon |
| **Vue** | 🚧 Planned | - | Coming soon |
| **Docker** | 🚧 Planned | - | Coming soon |
| **Docker Compose** | 🚧 Planned | - | Coming soon |
| **Shell Scripts** | 🚧 Planned | - | Coming soon |

### Rails (✅ Complete - 17 Modules)

Comprehensive Rails patterns and best practices extracted from production codebases.

**Quick Start:**
```markdown
# In your project's CLAUDE.md
@agent-notes/rails/index.md
```

**Includes:**
- **Core:** Models, Controllers, Routes, Concerns, Tests
- **Frontend:** Views, Helpers, JavaScript (Stimulus/Turbo)
- **Background:** Jobs, Mailers, Broadcasting
- **Data:** Migrations, Active Storage, Validations
- **Infrastructure:** Lib, Initializers
- **Code Style & Conventions**

**Documentation:** [rails/README.md](rails/README.md) | **Examples:** [rails/CLAUDE.md.example](rails/CLAUDE.md.example)
### Docker (✅ Complete - 2 Modules)

Production-ready Docker and Docker Compose patterns based on official Docker documentation.

**Quick Start:**
```markdown
# In your project's CLAUDE.md
@agent-notes/docker/index.md
```

**Includes:**
- **Dockerfile Patterns:** Multi-stage builds, security (non-root UID > 10,000), health checks, layer optimization
- **Docker Compose:** Service orchestration, health checks, dependencies, dev/prod configs
- **Security:** Official Docker security best practices, vulnerability scanning
- **Languages:** Node.js, Python, Ruby/Rails, Go patterns

**Documentation:** [docker/README.md](docker/README.md)

## How to Use

1. **Clone or copy this repo into your project:**
   ```bash
   cd /path/to/your/project
   git clone git@github.com:rubakas/agent-notes.git
   # or
   cp -r /path/to/agent-notes .
   ```

2. **Create or update your project's `CLAUDE.md`:**
   ```markdown
   # My Project

   ## Rails Best Practices

   @agent-notes/rails/index.md
   ```

3. **Optional - Include specific modules only:**
   ```markdown
   # My Project

   ## Rails Patterns

   @agent-notes/rails/models.md
   @agent-notes/rails/controllers.md
   @agent-notes/rails/style.md
   <!-- @agent-notes/rails/jobs.md -->  <!-- Disabled -->
   ```

4. **Add project-specific patterns:**
   ```markdown
   @agent-notes/rails/index.md

   ## Project-Specific Patterns

   @docs/architecture.md
   @docs/deployment.md
   ```

## Repository Structure

```
your-project/
├── agent-notes/          # This repository
│   ├── rails/            # Rails patterns and conventions
│   │   ├── README.md     # Rails documentation
│   │   ├── CLAUDE.md.example # Example configuration
│   │   ├── index.md     # ⭐ Entry point (includes all 17 modules)
│   │   ├── models.md
│   │   ├── controllers.md
│   │   └── ...          # 14 more modules
│   ├── docker/           # Docker and Docker Compose patterns
│   │   ├── README.md     # Docker documentation
│   │   ├── index.md     # ⭐ Entry point (includes all 2 modules)
│   │   ├── dockerfile.md
│   │   └── compose.md
│   ├── react/            # Coming soon (will have index.md)
│   ├── nextjs/           # Coming soon (will have index.md)
│   └── README.md         # This file
├── app/                  # Your application code
└── CLAUDE.md            # ⭐ Your project configuration
```

**Each technology folder has an entry point:**
- `agent-notes/rails/index.md` - All Rails modules
- `agent-notes/docker/index.md` - All Docker modules
- `agent-notes/react/index.md` - (Coming soon) All React modules
- `agent-notes/nextjs/index.md` - (Coming soon) All Next.js modules

**Your project's CLAUDE.md stays simple:**
```markdown
# My Project

@agent-notes/rails/index.md
@agent-notes/react/index.md
@agent-notes/nextjs/index.md
@agent-notes/docker/index.md
```

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
