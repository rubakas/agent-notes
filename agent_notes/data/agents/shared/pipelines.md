## Task pipelines

### Feature pipeline
explorer (discovery) → coder (implementation) → test-writer and tech-writer (docs, if user-facing) when the approved plan includes them → review per Phase 3

**Frontend addendum:** the browser-test gate in Phase 4.5 applies when the diff touches a rendered surface.

### Bugfix pipeline
debugger (when the root cause is unknown) or explorer (reproduce + locate) → coder (minimal fix + regression test) → review per Phase 3

### Audit pipeline (read-only)
[parallel: the audit agents the scope needs, from system-auditor, performance-profiler, security-auditor, database-specialist, api-reviewer] → lead synthesizes (no coder)

### Infra pipeline
devops (implementation) → review per Phase 3

### Research pipeline (read-only)
explorer → lead answers
