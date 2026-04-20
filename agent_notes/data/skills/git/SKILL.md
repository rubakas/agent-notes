---
name: git
description: "Git workflow: analyzing changes, chunking commits, conventional commit messages"
---

# Git Workflow

## Committing changes

When asked to commit, follow this process:

### 1. Analyze all changes

```bash
git status
git diff
git diff --cached
```

### 2. Chunk into logical commits

Group related changes into small, focused commits. Each commit should represent ONE logical change:
- Don't mix refactors with features
- Don't mix formatting with bug fixes
- Separate test changes if they cover different features
- New file + its test = one commit is fine

### 3. Stage and commit each chunk

For each logical chunk:

```bash
git add <specific files>
git commit -m "#<ticket> type(scope): short description"
```

### 4. Commit message format

```
#<ticket> type(scope): short description
```

- **No body, no description** — title only
- **Short** — under 72 characters
- **Lowercase** — no capital letters after the colon
- Extract ticket number from branch name when available

### 5. Extract ticket from branch

```bash
git branch --show-current
```

Patterns:
- `feature/123-description` → `#123`
- `fix/ABC-123-description` → `#ABC-123`
- `123-description` → `#123`
- No ticket found → omit prefix

### 6. Commit types

- `feat` — new feature or file
- `fix` — bug fix
- `refactor` — code restructuring, no behavior change
- `test` — test additions or changes
- `docs` — documentation only
- `chore` — config, tooling, dependencies
- `style` — formatting only
- `perf` — performance improvement

### 7. Scope

Derive from the primary area of change: `auth`, `api`, `models`, `ci`, `install`, `doctor`, etc.

## Examples

Single commit:
```
#142 feat(auth): add two-factor authentication via TOTP
```

Multiple logical chunks from one set of changes:
```
#89 fix(payments): handle nil amount in refund calculation
#89 test(payments): add specs for refund edge cases
```
