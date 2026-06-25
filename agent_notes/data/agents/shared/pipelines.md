## Task pipelines

### Feature pipeline
explorer (discovery) → coder (implementation) → [parallel: reviewer, test-writer, security-auditor (if auth/input/data)] → tech-writer (docs, if user-facing)

**Frontend addendum:** when the change touches the UI and is locally testable, the lead runs a `chrome-test` cycle via the profile-aware file bus by minting a uuid-d `request-<uuid>.md`, handing the operator only the request-file PATH to read (no copy/paste of content), and fetching the result directly from `report-<uuid>.md` (no paste-back). Multiple uuid-d requests can run in parallel; the lead may watch `progress-<uuid>.md` for long runs. Use Mode 1 (live/parallel) during iterative work or Mode 2 (end-state QC) once — after linters/tests pass, before commit.

### Bugfix pipeline
explorer (reproduce + locate) → coder (minimal fix + regression test) → reviewer (verify)

### Audit pipeline (read-only)
[parallel: system-auditor, performance-profiler, security-auditor, database-specialist, api-reviewer] → lead synthesizes (no coder)

### Infra pipeline
devops (implementation) → [parallel: reviewer, security-auditor]

### Research pipeline (read-only)
explorer → lead answers
