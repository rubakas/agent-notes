# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

- **New models now appear after an upgrade even if you once ran `models refresh`.** The catalog loader used `~/.cache/agent-notes/catalog.json` whenever it existed, so a single old refresh hid every model a later release shipped — the install wizard, `config role-model`, `list models` and build-time selection all read the stale list (this is how `claude-opus-5-5` went missing). The cache is now used only when its `fetched_at` is at least as new as the bundled catalog's. `models refresh` follows the same rule when it merges a single provider.

- **Guard-credentials no longer denies benign commands containing bare `.key`/`.pem`-style fragments** (e.g. jq selectors such as `"\(.key)"`). Secret-extension matching now requires a non-empty stem (`id_rsa.key` is still denied; a bare `.key` fragment is not), and the same stem requirement is applied to the basename patterns for `.pem`, `.p12`, `.pfx`, `.jks`, `.keystore`, and `.truststore`. The `.env` handling is unchanged — `.env` and `.env.production` remain denied via their dedicated pattern.

### Added

- **Synced Matt Pocock skills from upstream ([`391a270`](https://github.com/mattpocock/skills/commit/391a2701dd948f94f56a39f7533f8eea9a859c87), 2026-07-10).** New skills: `codebase-design`, `domain-modeling`, `grilling`, `research`, `triage`, `wayfinder`, `to-spec`, `to-tickets`, `diagnosing-bugs`, `writing-great-skills`, and `setup-agent-tracker` (the per-repo issue-tracker/triage/domain setup skill, de-branded from upstream's `setup-matt-pocock-skills`). Every imported skill was reviewed for prompt-injection, exfiltration, and destructive commands by an adversarial multi-agent pass before import. Run `agent-notes regenerate` to apply.
- **`no-ai-attribution` global rule.** Forbids any AI model (Claude or otherwise) from adding `Co-Authored-By` trailers, "Generated with", `🤖`, or any self-attribution to commit messages, PR titles/descriptions, code comments, or anywhere else. Distributed to all CLIs like the existing `safety` and `code-quality` rules; the `git` skill cross-references it.

- **"Decompose before delegating" rule in lead instructions.** Before dispatching a coder/refactorer/test-writer, the lead must convert investigation findings into an ordered `file → change → reason` checklist and pass concrete `file:line` findings verbatim, so executing agents run a batch instead of re-exploring already-mapped code. Adds a matching anti-pattern and coder/refactorer directives. Run `agent-notes regenerate` to apply.

### Changed

- **Recommended models for Claude Code and OpenCode: reasoner → `claude-opus-5-5`, worker → `claude-sonnet-5-5`** (were `claude-opus-5` / `claude-sonnet-5`). Both are not yet rated upstream, and an unrated model could never become a default, so `rules.yaml` gains a `provisional_coding_index` block: a hand-curated stand-in score used only while OpenRouter has no coding score, retired automatically once it does. Model tables mark it with `*` (e.g. `78.1*`). Orchestrator, scout and every Codex default are unchanged. Existing installs keep the models saved when they were installed — re-run `agent-notes install` to pick up the new recommendations.

- **Refreshed vendored Matt Pocock skills from upstream:** `code-review`, `tdd`, `grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `handoff`, `prototype`. Renamed to match upstream: `debugging-protocol` → `diagnosing-bugs`, `write-a-skill` → `writing-great-skills`, `setup-project-context` → `domain-modeling`, `to-prd` → `to-spec`, `to-issues` → `to-tickets`.
- **Plugin build now vendors full skill directories** (including bundled reference files such as `tdd/mocking.md`, `codebase-design/DEEPENING.md`) and prunes retired/renamed skills from `.claude-plugin/skills/` on each build, instead of copying only `SKILL.md` and leaving stale directories behind.

- **Cost reporting is now opt-in (default: disabled).** Previously, the per-response token-usage table was appended to every Claude Code / OpenCode response by default. It is now disabled for new installs. Existing users whose config does not contain `cost_report_enabled` will also see reporting disabled after upgrading. To opt in, run `agent-notes config cost-report on` then `agent-notes regenerate`.

- The install wizard now includes a step asking whether to enable cost reporting (default: No).

- Memory backend is now selected via a single flat menu: `default - Claude Code built-in md files` (default), `Obsidian - session`, `Obsidian - brain`, `None`.

- Chrome-test handoff uses uuid-correlated bus files (`request-<uuid>.md` / `progress-<uuid>.md` / `report-<uuid>.md`), path-only handoff, `X/N` step progress, and supports parallel requests.

### Removed

- Retired the `caveman` and `zoom-out` skills, which were removed from the upstream Matt Pocock repo (caveman was a private test skill; zoom-out went unused). `chrome-test` is retained as an agent-notes skill.
