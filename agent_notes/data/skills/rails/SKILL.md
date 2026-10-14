---
name: rails
group: domain
description: "Rails reference distilled from 37signals' Fizzy: ActiveRecord models, concerns, migrations, controllers, routes, views, Hotwire (Turbo/Stimulus), Solid Queue/Cache/Cable, Kamal, minitest. Use when working in a Rails codebase."
triggers:
  - rails
  - ActiveRecord
  - controller
  - model
  - migration
  - route
  - view
  - ERB
  - partial
  - ViewComponent
  - Stimulus
  - Turbo
  - morph
  - Action Cable
  - Solid Queue
  - Solid Cache
  - Solid Cable
  - Active Job
  - Active Storage
  - Action Mailer
  - Kamal
  - Thruster
  - Propshaft
  - Importmap
  - Current
  - multi-tenant
  - concern
  - scope
  - validation
  - callback
  - association
---

# Rails Reference

## Rules

- **Project RuboCop config wins.** Fizzy uses `rubocop-rails-omakase`, which enables neither `Style/GuardClause` nor `Layout/IndentationConsistency`, so lint enforces neither conditional style nor private indentation. Fizzy's STYLE.md is the 37signals default only when the project has no explicit rule; Fizzy's AGENTS.md calls its own instructions "defaults with reasons, not law". Use the project's `.rubocop.yml` to resolve ambiguities.
- **Teach the project's Rails version.** Fizzy runs Rails main (`rails 8.2.0.alpha`) and a `turbo-rails` branch (Gemfile.lock). Mark Fizzy-specific APIs that need Rails main (e.g., `Turbo.offline`) where they appear, and do not use them in production.
- **Concerns for shared model behaviour.** Put one capability of a model in a concern named for what it does (`Card::Closeable`), and behaviour shared by several models in `app/models/concerns/`. (Fizzy: `app/models/card.rb` includes 23 concerns; `app/models/concerns/`)
- **Vanilla CRUD: prefer a new resource over a custom action.** When an action doesn't fit a CRUD verb, introduce a resource (`resource :closure`) instead of a custom route (`post :close`). (Fizzy STYLE.md "CRUD controllers")
- **Rich models, thin controllers, no service layer.** Call model methods directly from controllers; avoid services unless strictly necessary. (Fizzy STYLE.md "Controller and model interactions")
- **No `default_scope`.** Scope explicitly through relationships (`Current.user.accessible_cards`). Fizzy defines no `default_scope`: a search of the repository at the pinned commit finds none. (Fizzy: `app/models/user/accessor.rb`)
- **`Current` for request-scoped context.** Keep the session, user and account in `Current` (`ActiveSupport::CurrentAttributes`) and default model arguments from it (`close(user: Current.user)`). (Fizzy: `app/models/current.rb`, `app/models/card/closeable.rb`)
- **Solid stack, not Redis, for new apps.** Use Solid Queue, Solid Cache and Solid Cable. Fizzy runs them on SQLite (`config/database.sqlite.yml`) or MySQL (`config/database.mysql.yml`) and its Gemfile has no Redis gem. Redis is optional only if the app already depends on it (Sidekiq, caching).
- **Async work through `_later` plus shallow jobs.** A model method that enqueues a job ends in `_later`, and the job's `perform` calls a plain model method (`card.remove_inaccessible_notifications`). STYLE.md names a synchronous twin `*_now`; Fizzy's models do not define one. (Fizzy STYLE.md "Run async operations in jobs"; `app/jobs/card/remove_inaccessible_notifications_job.rb`)
- **Minitest and fixtures.** Fizzy uses Minitest (Rails default) and fixtures, with no factories: `test/fixtures/` exists and the Gemfile has no RSpec or FactoryBot.
- **ViewComponent only if the project already uses it.** Added by the owner, not from Fizzy/37signals. Don't introduce it to projects that use partials: Fizzy renders with partials and helpers and has no `view_component` gem or `app/components`.

Provenance: distilled from Fizzy (github.com/basecamp/fizzy) at commit 6aebc0cea63d0e5fcdd2eeea138072ddcb26be74, reviewed 2026-10-05.
Also drawn from Fizzy's STYLE.md, AGENTS.md and dev.37signals.com articles; ViewComponent (view-components.md) is not from Fizzy.

### Models

| File | Read when … |
|---|---|
| [models-structure.md](models-structure.md) | Setting up models, associations (including delegated types), file structure, and model templates |
| [models-callbacks-jobs.md](models-callbacks-jobs.md) | Writing callbacks and enqueueing jobs from models via `_later` suffix |
| [models-attributes.md](models-attributes.md) | Validating attributes, enums, serialization, secure tokens, Action Text, UUID primary keys |
| [models-concerns.md](models-concerns.md) | Organizing model capabilities as concerns (feature and shared) |
| [models-current-tenancy.md](models-current-tenancy.md) | Using `Current` attributes in models and controllers, account-scoped associations, global identity records |
| [models-migrations.md](models-migrations.md) | Writing and structuring database migrations, indexes, foreign keys |

### Controllers, Routes and Helpers

| File | Read when … |
|---|---|
| [controllers-rest.md](controllers-rest.md) | Building REST controllers (CRUD, resource-action, nested), parameter handling, response patterns |
| [controllers-errors-auth.md](controllers-errors-auth.md) | Error handling, performance, API patterns, security, authentication in controllers |
| [routes.md](routes.md) | Routing: resources, custom routes, nested routes, namespaces, resource vs. custom action |
| [helpers.md](helpers.md) | View helpers: application, domain-specific, form, time helpers and best practices |

### Views and Frontend

| File | Read when … |
|---|---|
| [views.md](views.md) | Writing ERB templates, partials, layouts, forms, helpers, and Jbuilder |
| [view-caching.md](view-caching.md) | Fragment caching, HTTP caching with ETags, touch chains, Jbuilder caching |
| [view-components.md](view-components.md) | Using ViewComponent (added by the owner, not from Fizzy/37signals). Skip unless the project already uses it. |
| [stimulus.md](stimulus.md) | Stimulus controllers: structure, patterns (auto-submit, keyboard, dialog, toggle), file organization |
| [turbo.md](turbo.md) | Turbo Frames and Streams: lazy-load, morphing, refresh broadcasts, prefetch, view transitions |
| [broadcasting.md](broadcasting.md) | Broadcasting model changes: `broadcasts_refreshes`, `*_later_to` methods, Solid Cable config, multi-tenant |
| [importmap-assets.md](importmap-assets.md) | Importmap (JS pinning, audits), Propshaft (plain CSS, no build), Thruster (reverse proxy) |
| [active-storage.md](active-storage.md) | File attachments: variants, validations, storage services (S3, local, GCS) |

### Jobs, Mail and Storage

| File | Read when … |
|---|---|
| [jobs.md](jobs.md) | Active Job and Solid Queue: job structure, `_later` jobs, recurring jobs, error handling, testing |
| [mailers.md](mailers.md) | Action Mailer: structure, templates, previews, sending async, testing |

### Infrastructure and Deploy

| File | Read when … |
|---|---|
| [solid-stack.md](solid-stack.md) | Solid Queue, Solid Cache, Solid Cable: configuration, databases, migrations |
| [deploy-kamal.md](deploy-kamal.md) | Kamal 2 deployment: config/deploy.yml, Dockerfile, Thruster, entrypoint, secrets, hooks |
| [config-and-lib.md](config-and-lib.md) | Initializers, lib/ structure, Rails extensions, custom libraries |
| [multi-tenancy.md](multi-tenancy.md) | URL-based tenancy (the one home for tenancy code): routing, middleware, `Current`, tenant-aware mailers, cable, jobs, test setup |

### Testing

| File | Read when … |
|---|---|
| [testing-models-fixtures.md](testing-models-fixtures.md) | Model tests, fixtures, test structure, test helpers, running tests |
| [testing-controllers.md](testing-controllers.md) | Controller and integration tests, permissions, response formats |
| [testing-system-jobs-mailers.md](testing-system-jobs-mailers.md) | System tests (Capybara), job tests, mailer tests, helper tests |

### Style and CI

| File | Read when … |
|---|---|
| [code-style.md](code-style.md) | Code formatting: RuboCop config, conditionals, method order, bang methods, visibility |
| [ci-and-linting.md](ci-and-linting.md) | CI setup, GitHub Actions, RuboCop configuration, pre-commit hooks |

## Overlapping Files

- **multi-tenancy.md** holds the tenancy code once (middleware, `Current`, `AccountTenanted`, test setup); **models-current-tenancy.md** covers `Current` use in models and controllers and account-scoped associations.
- **models-callbacks-jobs.md** covers enqueueing jobs from models via `_later`; **jobs.md** covers job classes, queue configuration, and Solid Queue.
