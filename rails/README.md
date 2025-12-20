# Rails - Modular Reference

Comprehensive, modular Rails patterns and best practices. Each file can be independently included or excluded in CLAUDE.md.

---

## Available Modules

### Core Patterns
- **models.md** - Model structure, associations, validations, scopes, callbacks, transactions
- **controllers.md** - Controller structure, concerns, parameters, responses, error handling
- **routes.md** - RESTful routing, actions as resources, nested resources, custom routes
- **concerns.md** - Model and controller concerns, patterns, and best practices
- **tests.md** - Model, controller, system, integration tests, fixtures, helpers

### Views & Frontend
- **views.md** - Partials, Turbo Streams, JSON (Jbuilder), caching ✅
- **viewcomponents.md** - ViewComponent patterns, slots, testing, previews ✅
- **helpers.md** - View helpers, domain-specific helpers, application helpers ✅
- **javascript.md** - Stimulus controllers, Turbo, Hotwire patterns ✅

### Background & Communication
- **jobs.md** - Background job patterns, error handling, recurring jobs ✅
- **mailers.md** - Mailer patterns, layouts, testing ✅
- **broadcasting.md** - Turbo broadcasts, real-time updates ✅

### Database & Storage
- **migrations.md** - Migration patterns, indexes, UUID keys ✅
- **active_storage.md** - File uploads, attachments, validations ✅

### Infrastructure
- **lib.md** - Custom libraries, Rails extensions, monkey patches ✅
- **initializers.md** - Configuration, boot-time setup ✅
- **validations.md** - Custom validators, validation patterns ✅
- **kamal.md** - Deployment with Kamal, zero-downtime deploys, accessories ✅

---

## Usage

### Include All Modules (Recommended)

Single line includes everything:

```markdown
## Rails Best Practices

@agent-notes/rails/index.md
```

This loads all 17 Rails pattern modules automatically.

### Include Specific Modules Only

For granular control, include individual files:

```markdown
## Rails Patterns

@agent-notes/rails/models.md
@agent-notes/rails/controllers.md
@agent-notes/rails/routes.md
```

### Disable Specific Modules

Comment out any you don't need:

```markdown
@agent-notes/rails/index.md  <!-- Includes all modules -->

<!-- OR selective loading: -->

@agent-notes/rails/models.md
<!-- @agent-notes/rails/controllers.md -->  <!-- Disabled -->
@agent-notes/rails/routes.md
```

---

## File Organization

```
rails/
├── README.md              # This file
├── CLAUDE.md.example      # Example configuration
├── index.md              # ⭐ Entry point (includes all modules)
├── models.md             # ✅ Complete
├── controllers.md        # ✅ Complete
├── routes.md             # ✅ Complete
├── concerns.md           # ✅ Complete
├── tests.md              # ✅ Complete
├── style.md              # ✅ Complete
├── views.md              # ✅ Complete
├── viewcomponents.md     # ✅ Complete
├── helpers.md            # ✅ Complete
├── javascript.md         # ✅ Complete
├── jobs.md               # ✅ Complete
├── mailers.md            # ✅ Complete
├── broadcasting.md       # ✅ Complete
├── migrations.md         # ✅ Complete
├── active_storage.md     # ✅ Complete
├── lib.md                # ✅ Complete
├── initializers.md       # ✅ Complete
├── validations.md        # ✅ Complete
└── kamal.md              # ✅ Complete
```

---

## Pattern Overview

Each file follows this structure:

1. **Philosophy** - Core principles
2. **File Structure** - Where files go
3. **Templates** - Copy-paste ready templates
4. **Patterns** - Real-world examples
5. **Best Practices** - Do's and don'ts
6. **Testing** - How to test
7. **Summary** - Quick reference

---

## Quick Reference

### Where Should Code Go?

```
Business Logic        → models.md (model methods/concerns)
HTTP Handling        → controllers.md (thin controllers)
Routes/URLs          → routes.md (RESTful resources)
View Logic           → helpers.md (presentation only)
State Toggles        → routes.md (singleton resources)
Background Work      → jobs.md (delegates to models)
Shared Behavior      → concerns.md (model/controller concerns)
Database Schema      → migrations.md (version-controlled)
File Uploads         → active_storage.md (attachments)
Rich Text            → active_text.md (Action Text)
Configuration        → initializers.md (boot-time)
Framework Extensions → lib.md (monkey patches)
```

### Common Patterns

**Feature Implementation:**
1. Model concern (`models.md` + `concerns.md`)
2. Controller (`controllers.md`)
3. Singleton resource route (`routes.md`)
4. Tests (`tests.md`)

**CRUD Resource:**
1. Model (`models.md`)
2. Controller (`controllers.md`)
3. RESTful routes (`routes.md`)
4. Views (TBD: `views.md`)
5. Tests (`tests.md`)

---

## Contributing

When adding patterns from other Rails apps:

1. **Keep it generic** - Remove app-specific references
2. **Show examples** - Include code samples
3. **Explain why** - Document the reasoning
4. **Test patterns** - Show how to test
5. **Follow structure** - Match existing file format

---

## Summary

These are modular, comprehensive references for Rails development patterns. Include what you need, exclude what you don't. Each file is self-contained and can be used independently.
