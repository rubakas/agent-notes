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
| **Rails** | ✅ Complete | 17 modules | `@rails/index.md` |
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
@rails/index.md
```

**Includes:**
- **Core:** Models, Controllers, Routes, Concerns, Tests
- **Frontend:** Views, Helpers, JavaScript (Stimulus/Turbo)
- **Background:** Jobs, Mailers, Broadcasting
- **Data:** Migrations, Active Storage, Validations
- **Infrastructure:** Lib, Initializers
- **Code Style & Conventions**

**Documentation:** [rails/README.md](rails/README.md) | **Examples:** [rails/CLAUDE.md.example](rails/CLAUDE.md.example)

## How to Use

1. **Copy to your project:**
   ```bash
   # Example: Add Rails patterns to your project
   cp -r rails /path/to/your/project/
   ```

2. **Create or update your project's `CLAUDE.md`:**
   ```markdown
   # My Project

   ## Rails Best Practices

   @rails/index.md
   ```

3. **Optional - Include specific modules only:**
   ```markdown
   # My Project

   ## Rails Patterns

   @rails/models.md
   @rails/controllers.md
   @rails/style.md
   <!-- @rails/jobs.md -->  <!-- Disabled -->
   ```

4. **Add project-specific patterns:**
   ```markdown
   @rails/index.md

   ## Project-Specific Patterns

   @docs/architecture.md
   @docs/deployment.md
   ```

## Structure

```
agent-notes/
├── rails/                # Rails patterns and conventions
│   ├── README.md         # Rails documentation
│   ├── CLAUDE.md.example # Example configuration
│   ├── index.md         # ⭐ Entry point (includes all modules)
│   ├── models.md         # Model patterns
│   ├── controllers.md    # Controller patterns
│   └── ...               # Additional modules (17 total)
├── react/                # Coming soon (will have index.md entry point)
├── nextjs/               # Coming soon (will have index.md entry point)
└── README.md             # This file
```

**Each folder has an entry point file:**
- `rails/index.md` - Includes all Rails modules
- `react/index.md` - (Coming soon) Includes all React modules
- `nextjs/index.md` - (Coming soon) Includes all Next.js modules

**This means your project's CLAUDE.md stays simple:**
```markdown
# My Project

@rails/index.md
@react/index.md
@nextjs/index.md
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
