# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **Synced Matt Pocock skills from upstream ([`391a270`](https://github.com/mattpocock/skills/commit/391a2701dd948f94f56a39f7533f8eea9a859c87), 2026-07-10).** New skills: `codebase-design`, `domain-modeling`, `grilling`, `research`, `triage`, `wayfinder`, `to-spec`, `to-tickets`, `diagnosing-bugs`, `writing-great-skills`, and `setup-agent-tracker` (the per-repo issue-tracker/triage/domain setup skill, de-branded from upstream's `setup-matt-pocock-skills`). Every imported skill was reviewed for prompt-injection, exfiltration, and destructive commands by an adversarial multi-agent pass before import. Run `agent-notes regenerate` to apply.
- **`no-ai-attribution` global rule.** Forbids any AI model (Claude or otherwise) from adding `Co-Authored-By` trailers, "Generated with", `🤖`, or any self-attribution to commit messages, PR titles/descriptions, code comments, or anywhere else. Distributed to all CLIs like the existing `safety` and `code-quality` rules; the `git` skill cross-references it.

- **"Decompose before delegating" rule in lead instructions.** Before dispatching a coder/refactorer/test-writer, the lead must convert investigation findings into an ordered `file → change → reason` checklist and pass concrete `file:line` findings verbatim, so executing agents run a batch instead of re-exploring already-mapped code. Adds a matching anti-pattern and coder/refactorer directives. Run `agent-notes regenerate` to apply.

### Changed

- **Refreshed vendored Matt Pocock skills from upstream:** `code-review`, `tdd`, `grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `handoff`, `prototype`. Renamed to match upstream: `debugging-protocol` → `diagnosing-bugs`, `write-a-skill` → `writing-great-skills`, `setup-project-context` → `domain-modeling`, `to-prd` → `to-spec`, `to-issues` → `to-tickets`.
- **Plugin build now vendors full skill directories** (including bundled reference files such as `tdd/mocking.md`, `codebase-design/DEEPENING.md`) and prunes retired/renamed skills from `.claude-plugin/skills/` on each build, instead of copying only `SKILL.md` and leaving stale directories behind.

- **Cost reporting is now opt-in (default: disabled).** Previously, the per-response token-usage table was appended to every Claude Code / OpenCode response by default. It is now disabled for new installs. Existing users whose config does not contain `cost_report_enabled` will also see reporting disabled after upgrading. To opt in, run `agent-notes config cost-report on` then `agent-notes regenerate`.

- The install wizard now includes a step asking whether to enable cost reporting (default: No).

- Memory backend is now selected via a single flat menu: `default - Claude Code built-in md files` (default), `Obsidian - session`, `Obsidian - brain`, `None`.

- Chrome-test handoff uses uuid-correlated bus files (`request-<uuid>.md` / `progress-<uuid>.md` / `report-<uuid>.md`), path-only handoff, `X/N` step progress, and supports parallel requests.

### Removed

- Retired the `caveman` and `zoom-out` skills, which were removed from the upstream Matt Pocock repo (caveman was a private test skill; zoom-out went unused). `chrome-test` is retained as an agent-notes skill.
