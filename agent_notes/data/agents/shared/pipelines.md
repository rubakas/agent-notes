## Task pipelines

### Feature pipeline
explorer (discovery) → coder (implementation) → [parallel: reviewer, test-writer, security-auditor (if auth/input/data)] → tech-writer (docs, if user-facing)

### Bugfix pipeline
explorer (reproduce + locate) → coder (minimal fix + regression test) → reviewer (verify)

### Audit pipeline (read-only)
[parallel: system-auditor, performance-profiler, security-auditor, database-specialist, api-reviewer] → lead synthesizes (no coder)

### Infra pipeline
devops (implementation) → [parallel: reviewer, security-auditor]

### Research pipeline (read-only)
explorer → lead answers
