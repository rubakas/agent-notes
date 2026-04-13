# Safety

- Confirm before destructive or irreversible operations:
  - `git push --force`, `git reset --hard`, amending published commits
  - `rm -rf`, deleting files or branches, dropping database tables
  - Operations visible to others: pushing code, commenting on PRs/issues
- Never commit secrets: `.env`, `*.pem`, credentials, API keys, tokens.
- Never bypass safety checks (`--no-verify`, `--force`) without explicit user request.
- Never force-push to main or master branches.
- When encountering obstacles, do not use destructive actions as shortcuts.
