---
name: rails
group: domain
description: "Rails development: models, controllers, views, testing, frontend, and infrastructure. Context7-style: loads only the relevant reference on demand."
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
  - Action Cable
  - Active Job
  - Active Storage
  - Action Mailer
  - Kamal
  - concern
  - scope
  - validation
  - callback
  - association
---

# Rails Reference

Based on the user's current task, use the Read tool to load the relevant reference file from this skill's directory. Only load the file(s) you need — do not load all of them.

| Topic | File | Use when |
|---|---|---|
| Models | models.md | ActiveRecord models, associations, callbacks, scopes, validations, concerns, migrations, enums, transactions |
| Controllers | controllers.md | Controllers, routes, helpers, parameter handling, filters, error handling, API patterns |
| Views | views.md | ERB templates, partials, layouts, forms, caching, ViewComponent, slots, previews |
| Testing | testing.md | Model specs, controller/request specs, system tests, fixtures, test helpers |
| Frontend | frontend.md | Stimulus controllers, Turbo Drive/Frames/Streams, broadcasting, Importmap, Active Storage |
| Infrastructure | infra.md | Active Job, Action Mailer, Kamal deployment, initializers, lib/, Rails style conventions |

The reference files are in the same directory as this skill file. After reading, apply the patterns and conventions to the user's code.
