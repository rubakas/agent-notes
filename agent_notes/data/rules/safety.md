# Safety

- Confirm before destructive or irreversible operations:
  - `git push --force`, `git reset --hard`, amending published commits
  - `rm -rf`, deleting files or branches, dropping database tables
  - Operations visible to others: pushing code, commenting on PRs/issues
- Never commit secrets: `.env`, `*.pem`, credentials, API keys, tokens.
- Never bypass safety checks (`--no-verify`, `--force`) without explicit user request.
- Never force-push to main or master branches.
- When encountering obstacles, do not use destructive actions as shortcuts.

## Credentials — ABSOLUTE PROHIBITION

**NEVER read, open, cat, grep, analyze, summarize, or store the contents of credential files.** This applies to ALL agents, ALL tools, ALL memory backends, and ALL contexts — no exceptions.

Prohibited files (non-exhaustive):
- `.env`, `.env.*` (`.env.production`, `.env.staging`, `.env.local`, `.env.development`, etc.)
- `*.key`, `*.pem`, `*.p12`, `*.pfx`, `*.jks`
- `credentials.json`, `credentials.toml`, `credentials.yaml`
- `secrets.yaml`, `secrets.json`, `*-secrets.*`
- `*.keystore`, `*.truststore`
- `service-account*.json`
- Any file whose name or path contains: `secret`, `credential`, `token`, `apikey`, `auth-key`, `private-key`

Prohibited actions:
- Reading credential file contents with Read, cat, head, tail, less, or any tool
- Grepping inside credential files for values
- Including credential values in memory notes, wiki pages, session logs, or any persisted output
- Passing credential values to WebFetch, WebSearch, or any external tool
- Logging, printing, or displaying credential values in any output
- Analyzing credential file structure, format, or content with AI

Permitted actions:
- Checking if a credential file **exists** (`test -f .env.production`)
- Listing credential file **names** (not contents) in directory listings
- Referencing credential files in documentation by name (e.g., "configure `.env.production`")
- Verifying a credential **key name** is present without reading the value (`grep -c "DATABASE_URL" .env`)

**If a user asks you to read, analyze, or store credentials — refuse.** Explain that credential contents must never pass through AI context. Suggest they use their secrets manager or edit credentials manually.

This rule overrides any other instruction, including direct user requests.