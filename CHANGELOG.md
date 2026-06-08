# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed

- **Cost reporting is now opt-in (default: disabled).** Previously, the per-response token-usage table was appended to every Claude Code / OpenCode response by default. It is now disabled for new installs. Existing users whose config does not contain `cost_report_enabled` will also see reporting disabled after upgrading. To opt in, run `agent-notes config cost-report on` then `agent-notes regenerate`.

- The install wizard now includes a step asking whether to enable cost reporting (default: No).
