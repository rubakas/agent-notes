# AI Agent Notes

Modular configuration files and best practices for AI coding agents. This repository provides reusable guides that help AI assistants understand your project's patterns and conventions.

## Purpose

AI coding agents work best when they have clear, structured context about your codebase. This repository collects modular configuration files that you can copy into your projects to provide that context automatically.

Instead of explaining patterns repeatedly in every conversation, you can reference these guides once in your project's `CLAUDE.md` or `AGENTS.md` file, and the AI will have comprehensive knowledge of your tech stack's best practices.

## Available Guides

### Rails

Comprehensive Rails patterns and best practices extracted from production codebases.

**Location:** `rails/`

**Usage:** Copy `rails/CLAUDE.md.example` to your project as `CLAUDE.md` and customize which modules to include.

**Covers:**
- Models, Controllers, Routes, Concerns
- Views, Helpers, JavaScript (Stimulus/Turbo)
- Background Jobs, Mailers, Broadcasting
- Migrations, Active Storage
- Testing, Validations
- Code Style & Conventions

See [rails/README.md](rails/README.md) for details.

## Coming Soon

- **React** - Component patterns, hooks, state management
- **Next.js** - App Router, Server Components, routing patterns
- **Vue** - Composition API, component structure, Pinia
- **Docker** - Dockerfile best practices, multi-stage builds
- **Docker Compose** - Service orchestration, networking
- **Shell Scripts** - Bash scripting patterns and conventions

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

   @rails/models.md
   @rails/controllers.md
   @rails/style.md
   ```

3. **Customize which modules to include:**
   - Enable only what you need
   - Comment out what you don't want
   - Add project-specific documentation alongside

## Structure

```
agent-notes/
├── rails/                # Rails patterns and conventions
│   ├── README.md         # Rails documentation
│   ├── CLAUDE.md.example # Example configuration
│   ├── models.md         # Model patterns
│   ├── controllers.md    # Controller patterns
│   └── ...               # Additional modules
├── react/                # Coming soon
├── nextjs/               # Coming soon
└── README.md             # This file
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
