# Global Instructions

## Coding philosophy

- Read existing code before writing new code. Match project patterns.
- Minimal changes: only what was requested. Do not refactor beyond scope.
- Fix root causes, not symptoms.
- One approach, commit to it. Course-correct only on new evidence.

## Behavior

- Investigate before answering. Never speculate about code you haven't read.
- No over-engineering: no extra features, abstractions, or configs beyond scope.
- No comments or docs on code you didn't change.
- When the task is unclear, ask one clarifying question instead of guessing.

## Safety

- Confirm before: `git push --force`, `rm -rf`, `DROP TABLE`, branch deletion.
- Never commit: `.env`, `*.pem`, credentials, API keys, secrets.
- Never bypass: `--no-verify`, `--force` without explicit user request.
- Never force-push to main/master.

## Commits

- Format: `#<ticket> type(scope): short description`
- Extract ticket number from branch name when available.
- Types: feat, fix, refactor, test, docs, chore, style, perf

## Agent delegation

- Use subagents when tasks can run in parallel or require isolated context.
- For simple tasks, sequential operations, or single-file edits, work directly.
- Use `explorer` (Haiku) for quick lookups to save context tokens.
- Use `database-specialist` for schema, indexes, and query analysis.
- Use `performance-profiler` for bottleneck identification.
- Use `api-reviewer` for API design and consistency checks.
- Use `lead` for complex multi-step tasks requiring coordination.
