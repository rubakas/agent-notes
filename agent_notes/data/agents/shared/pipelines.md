## Task pipelines

### Feature pipeline
explorer (discovery) → coder (implementation) → [parallel: reviewer, test-writer, security-auditor (if auth/input/data)] → tech-writer (docs, if user-facing)

**Frontend addendum:** chrome-test is a gate with an objective trigger, not optional judgment. It fires when `git diff --name-only` touches a rendered surface (templates, components, stylesheets/CSS, views, or route handlers that emit HTML); skip it only when the diff touches none of those (pure logic, data, config, types, copy-only, or refactors with green tests). Unit/integration tests are the always-on baseline — chrome-test is additive, covering the visual/layout/interaction failure class unit tests structurally cannot, so neither replaces the other. When it fires, mint a uuid-d `request-<uuid>.md`, hand the operator only the request-file PATH (no content copy/paste), and read results from `report-<uuid>.md` (no paste-back); watch `progress-<uuid>.md` for long runs and run multiple uuid-d requests in parallel as needed. Two modes: Mode 1 (live/parallel) during iterative work, or Mode 2 (end-state QC) once after linters/tests pass, before commit. If no operator/live chrome session is available, write the `request-<uuid>.md`, mark the browser test DEFERRED — pending operator, and do not claim the gate fully closed.

### Bugfix pipeline
explorer (reproduce + locate) → coder (minimal fix + regression test) → reviewer (verify)

### Audit pipeline (read-only)
[parallel: system-auditor, performance-profiler, security-auditor, database-specialist, api-reviewer] → lead synthesizes (no coder)

### Infra pipeline
devops (implementation) → [parallel: reviewer, security-auditor]

### Research pipeline (read-only)
explorer → lead answers
