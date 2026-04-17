---
name: commit
description: "Creates a conventional commit message from staged changes and current branch name"
---

# Smart Commit

Create a commit message following conventional commit format, extracted from the current branch and staged changes.

## Steps

1. Get the current branch name:
   ```bash
   git branch --show-current
   ```

2. Extract ticket number from the branch name. Common patterns:
   - `feature/123-description` → `#123`
   - `fix/ABC-123-description` → `#ABC-123`
   - `123-description` → `#123`
   - No ticket found → omit ticket prefix

3. Analyze staged changes:
   ```bash
   git diff --cached --stat
   git diff --cached
   ```

4. Determine the commit type from the changes:
   - New files/features → `feat`
   - Bug fixes → `fix`
   - Code restructuring → `refactor`
   - Test additions/changes → `test`
   - Documentation only → `docs`
   - Config/tooling → `chore`
   - Formatting only → `style`
   - Performance improvements → `perf`

5. Determine scope from the primary area of change (e.g., `auth`, `api`, `models`).

6. Generate the commit message:
   ```
   #<ticket> type(scope): concise description of what changed and why
   ```

7. Present the message for user approval before committing.

## Examples

- `#142 feat(auth): add two-factor authentication via TOTP`
- `#89 fix(payments): handle nil amount in refund calculation`
- `refactor(models): extract address validation into concern`
- `#301 test(api): add request specs for user endpoints`
