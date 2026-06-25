# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **"Decompose before delegating" rule in lead instructions.** Before dispatching a coder/refactorer/test-writer, the lead must convert investigation findings into an ordered `file → change → reason` checklist and pass concrete `file:line` findings verbatim, so executing agents run a batch instead of re-exploring already-mapped code. Adds a matching anti-pattern and coder/refactorer directives. Run `agent-notes regenerate` to apply.

### Changed

- **Cost reporting is now opt-in (default: disabled).** Previously, the per-response token-usage table was appended to every Claude Code / OpenCode response by default. It is now disabled for new installs. Existing users whose config does not contain `cost_report_enabled` will also see reporting disabled after upgrading. To opt in, run `agent-notes config cost-report on` then `agent-notes regenerate`.

- The install wizard now includes a step asking whether to enable cost reporting (default: No).

- Memory backend is now selected via a single flat menu: `default - Claude Code built-in md files` (default), `Obsidian - session`, `Obsidian - brain`, `None`.

- Chrome-test handoff uses uuid-correlated bus files (`request-<uuid>.md` / `progress-<uuid>.md` / `report-<uuid>.md`), path-only handoff, `X/N` step progress, and supports parallel requests.
