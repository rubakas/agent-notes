# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

- **Esc no longer confirms a choice, and a bare Esc no longer waits for two more keys.** Esc now always means back/cancel and is recognized immediately. `NO_COLOR` is honoured. `agent-notes config` no longer exits with "No local installation found" when run outside a project with only local installs. Config saves regenerate the install that was edited, not whichever one auto-detection finds. A failed restore after declining an install is now reported, and Ctrl-C at the install question restores `dist/`.

- **Regenerating a local install from another folder writes into that install's project.** `regenerate` placed a local install's rules, `CLAUDE.md` and skills relative to the folder it ran from, so saving `agent-notes config` for a local install elsewhere wrote them into the current folder (run from `~`: into `~/.claude` and `~/CLAUDE.md`). They now go into the install's own project, and config refuses to save an install whose folder no longer exists.

- **Ctrl-C and a closed terminal cancel cleanly.** `install` and `config` print "Cancelled." instead of a traceback, and every way out of the install question — a no, Ctrl-C during the build, line mode's Ctrl-C or Ctrl-D — restores `dist/`. In line mode, "Discard N changes?" now defaults to No.

- **A config save whose regenerate fails says what was saved.** The footer reads "State saved; regenerate failed — run agent-notes regenerate: <error>" and the saved settings stop counting as unsaved edits (before, `q` offered to discard changes already written and `s` wrote them again). Other failure messages lead with the instruction so it survives an 80-column cut.

- **Review screen fixes.** A long header keeps its end (project and profile) by cutting the middle; a long text value shows its tail and the cursor; the API-key field no longer reveals the key's length, and a key that cannot be written is reported without ending the session; the read-only Install row names `agent-notes install --reconfigure` in full; the Models column lines up for `orchestrator`; `config show` piped to a file or pipe is no longer cut at 100 columns.

- **New models now appear after an upgrade even if you once ran `models refresh`.** The catalog loader used `~/.cache/agent-notes/catalog.json` whenever it existed, so a single old refresh hid every model a later release shipped — the install wizard, `config role-model`, `list models` and build-time selection all read the stale list (this is how `claude-opus-5-5` went missing). The cache is now used only when its `fetched_at` is at least as new as the bundled catalog's. `models refresh` follows the same rule when it merges a single provider.

- **Guard-credentials no longer denies benign commands containing bare `.key`/`.pem`-style fragments** (e.g. jq selectors such as `"\(.key)"`). Secret-extension matching now requires a non-empty stem (`id_rsa.key` is still denied; a bare `.key` fragment is not), and the same stem requirement is applied to the basename patterns for `.pem`, `.p12`, `.pfx`, `.jks`, `.keystore`, and `.truststore`. The `.env` handling is unchanged — `.env` and `.env.production` remain denied via their dedicated pattern.

### Added

- **Synced Matt Pocock skills from upstream ([`391a270`](https://github.com/mattpocock/skills/commit/391a2701dd948f94f56a39f7533f8eea9a859c87), 2026-07-10).** New skills: `codebase-design`, `domain-modeling`, `grilling`, `research`, `triage`, `wayfinder`, `to-spec`, `to-tickets`, `diagnosing-bugs`, `writing-great-skills`, and `setup-agent-tracker` (the per-repo issue-tracker/triage/domain setup skill, de-branded from upstream's `setup-matt-pocock-skills`). Every imported skill was reviewed for prompt-injection, exfiltration, and destructive commands by an adversarial multi-agent pass before import. Run `agent-notes regenerate` to apply.
- **`no-ai-attribution` global rule.** Forbids any AI model (Claude or otherwise) from adding `Co-Authored-By` trailers, "Generated with", `🤖`, or any self-attribution to commit messages, PR titles/descriptions, code comments, or anywhere else. Distributed to all CLIs like the existing `safety` and `code-quality` rules; the `git` skill cross-references it.

- **"Decompose before delegating" rule in lead instructions.** Before dispatching a coder/refactorer/test-writer, the lead must convert investigation findings into an ordered `file → change → reason` checklist and pass concrete `file:line` findings verbatim, so executing agents run a batch instead of re-exploring already-mapped code. Adds a matching anti-pattern and coder/refactorer directives. Run `agent-notes regenerate` to apply.

### Changed

- **The install wizard and the interactive `config` menu are replaced by one review screen.** `agent-notes install` opens it with every setting pre-filled: ↑↓ move, ⏎ edits a row, ←→ changes simple values, `i` installs (quiet build, then "Install N files (M backed up)?"), `q` quits. `agent-notes config` opens the same screen on an existing install (the current folder's, else global, else a picker): `tab` switches installs, `u` moves deprecated or unknown pins to the recommended model, `s` shows the diff and saves everything with one state write and one regenerate; API keys save as soon as entered. Terminals under 60×16 (or without `termios`) get numbered prompts. With no terminal, `install` installs the recommended setup without prompts — piped answers are no longer read. Scriptable `config` subcommands and `install --local/--copy/--profile/--folder/--global-home` are unchanged. `config show` uses the same layout and flags outdated pins.

- **Recommended models for Claude Code and OpenCode: reasoner → `claude-opus-5-5`, worker → `claude-sonnet-5-5`** (were `claude-opus-5` / `claude-sonnet-5`). Both are not yet rated upstream, and an unrated model could never become a default, so `rules.yaml` gains a `provisional_coding_index` block: a hand-curated stand-in score used only while OpenRouter has no coding score, retired automatically once it does. Model tables mark it with `*` (e.g. `78.1*`). Orchestrator, scout and every Codex default are unchanged. Existing installs keep the models saved when they were installed — re-run `agent-notes install` to pick up the new recommendations.

- **Refreshed vendored Matt Pocock skills from upstream:** `code-review`, `tdd`, `grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `handoff`, `prototype`. Renamed to match upstream: `debugging-protocol` → `diagnosing-bugs`, `write-a-skill` → `writing-great-skills`, `setup-project-context` → `domain-modeling`, `to-prd` → `to-spec`, `to-issues` → `to-tickets`.
- **Plugin build now vendors full skill directories** (including bundled reference files such as `tdd/mocking.md`, `codebase-design/DEEPENING.md`) and prunes retired/renamed skills from `.claude-plugin/skills/` on each build, instead of copying only `SKILL.md` and leaving stale directories behind.

- **Cost reporting is now opt-in (default: disabled).** Previously, the per-response token-usage table was appended to every Claude Code / OpenCode response by default. It is now disabled for new installs. Existing users whose config does not contain `cost_report_enabled` will also see reporting disabled after upgrading. To opt in, run `agent-notes config cost-report on` then `agent-notes regenerate`.

- Cost reporting is a "Cost report" row on the install review screen (default: off).

- Memory is a "Memory" row on the review screen: `built-in` (default) or `Obsidian` (single-brain or per-project strategy).

- Chrome-test handoff uses uuid-correlated bus files (`request-<uuid>.md` / `progress-<uuid>.md` / `report-<uuid>.md`), path-only handoff, `X/N` step progress, and supports parallel requests.

### Removed

- Retired the `caveman` and `zoom-out` skills, which were removed from the upstream Matt Pocock repo (caveman was a private test skill; zoom-out went unused). `chrome-test` is retained as an agent-notes skill.
