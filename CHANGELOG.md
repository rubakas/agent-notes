# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

- **`doctor` and `doctor --fix` work again.** Both crashed with an `ImportError` in the stale-file check (the installer module had moved), so no check ever ran. A test now verifies that every `from X import name` in the package resolves.

- **`set role` works again.** It crashed after saving the pin, on a wrong import for the regenerate step.

- **`regenerate` restores everything after a pipx reinstall or upgrade, and no longer adds or drops CLIs.** A reinstall leaves the package without its rendered `dist/`, and `regenerate` only re-placed agents, so rules, skills, commands and `CLAUDE.md` stayed dangling links while it printed "✓" for each. It now renders `dist/` first (the same build `install` runs) and places every component, commands included. It also kept recording every CLI that had content in `dist/`, widening or shrinking the install; it now keeps exactly the CLIs you installed. The agent count no longer includes files whose path merely contains the CLI's name ("Regenerated 55 files" for 18 agents).

- **A missing source is an error, not a success.** a missing agents configuration used to make `build` print "Error" and exit 0, and it now exits 1; an invalid one is now reported cleanly ("Build failed: …", exit 1) instead of a traceback; a fresh `install` whose build fails now exits 1 too; `regenerate` exits 1 naming the CLI and component when nothing was rendered for it; and `install` on an existing install reports a failed rebuild as an error instead of a warning followed by "Installation is healthy".

- **`install`'s verify step reports broken links.** An installed link whose target no longer exists counted as present; it is now reported as missing.

- **`q` at the install confirmation quits the installer.** It ignored the key; it now restores `dist/` and prints "Installation cancelled." like `q` on the review screen (footer: `⏎ yes · esc back · q quit`, line mode `[Y/n/q]`). In `config`, `q` at "Apply N changes?" and "Discard N changes?" means no and never discards.

- **Esc no longer confirms a choice, and a bare Esc no longer waits for two more keys.** Esc now always means back/cancel and is recognized immediately. `NO_COLOR` is honoured. `agent-notes config` no longer exits with "No local installation found" when run outside a project with only local installs. Config saves regenerate the install that was edited, not whichever one auto-detection finds. A failed restore after declining an install is now reported, and Ctrl-C at the install question restores `dist/`.

- **Regenerating a local install from another folder writes into that install's project.** `regenerate` placed a local install's rules, `CLAUDE.md` and skills relative to the folder it ran from, so saving `agent-notes config` for a local install elsewhere wrote them into the current folder (run from `~`: into `~/.claude` and `~/CLAUDE.md`). They now go into the install's own project, and config refuses to save an install whose folder no longer exists.

- **Ctrl-C and a closed terminal cancel cleanly.** `install` and `config` print "Cancelled." instead of a traceback, and every way out of the install question — a no, Ctrl-C during the build, line mode's Ctrl-C or Ctrl-D — restores `dist/`. In line mode, "Discard N changes?" now defaults to No.

- **A config save whose regenerate fails says what was saved.** The footer reads "State saved; regenerate failed — run agent-notes regenerate: <error>" and the saved settings stop counting as unsaved edits (before, `q` offered to discard changes already written and `s` wrote them again). Other failure messages lead with the instruction so it survives an 80-column cut.

- **Review screen fixes.** A long header keeps its end (project and profile) by cutting the middle; a long text value shows its tail and the cursor; the API-key field no longer reveals the key's length, and a key that cannot be written is reported without ending the session; the read-only Install row names `agent-notes install --reconfigure` in full; the Models column lines up for `orchestrator`; `config show` piped to a file or pipe is no longer cut at 100 columns.

- **New models now appear after an upgrade even if you once ran `models refresh`.** The catalog loader used `~/.cache/agent-notes/catalog.json` whenever it existed, so a single old refresh hid every model a later release shipped — the install wizard, `config role-model`, `list models` and build-time selection all read the stale list (this is how `claude-opus-5-5` went missing). The cache is now used only when its `fetched_at` is at least as new as the bundled catalog's. `models refresh` follows the same rule when it merges a single provider.

- **Guard-credentials no longer denies benign commands containing bare `.key`/`.pem`-style fragments** (e.g. jq selectors such as `"\(.key)"`). Secret-extension matching now requires a non-empty stem (`id_rsa.key` is still denied; a bare `.key` fragment is not), and the same stem requirement is applied to the basename patterns for `.pem`, `.p12`, `.pfx`, `.jks`, `.keystore`, and `.truststore`. The `.env` handling is unchanged — `.env` and `.env.production` remain denied via their dedicated pattern.

- **Memory and plugin choices apply in the same install,** not one install later. Before, a memory or plugin toggle changed the saved state *after* the confirm step, so the new value didn't reach the render or the session hook until the next install. They are now persisted only after a successful confirm, and the hook reads the newly saved values immediately.

- **An unreadable `state.json` stops the command** with exit 2 and a message naming the file, instead of being treated as empty, which could overwrite other installs' records.

- **`build` no longer keeps rules or agents that were removed from the package.** Removed items are now pruned from `dist/rules` and `dist/<cli>/agents` once the agents and rules are rendered, before the skills and commands are copied, so they stop being installed.

### Added

- **`browser-tester` agent (Claude Code only).** It runs a `chrome-test` request in the user's Chrome through the Claude-in-Chrome tools, overwrites `progress-<uuid>.md` after each step, and returns the report as its final message, because Claude Code refuses report files written by subagents. It is excluded from OpenCode and Codex.

- **Claude Haiku 5.5 added to the model catalog and priced at its own rate;** it becomes the default scout model via a provisional coding score.

- **Model catalog refreshed against the vendor docs.** The retired `claude-sonnet-4` and `claude-opus-4-1` are removed, and `gpt-6.1-terra` is added (priced at its own rate, classed as the middle tier). Deprecations now follow Anthropic's and OpenAI's pages: `claude-opus-4-5`, `claude-opus-4-6` and `claude-opus-4-7` are active again, while `gpt-5-mini`, `gpt-5-nano`, `gpt-5.1` and `gpt-5.4-nano` are deprecated. Claude Sonnet 5.5 is priced at its own rate, with cache reads at $0.10 per million tokens instead of Sonnet 5's $0.20. The restricted `gpt-5.6-cyber` stays out of the catalog.

- **Synced Matt Pocock skills from upstream ([`391a270`](https://github.com/mattpocock/skills/commit/391a2701dd948f94f56a39f7533f8eea9a859c87), 2026-07-10).** New skills: `codebase-design`, `domain-modeling`, `grilling`, `research`, `triage`, `wayfinder`, `to-spec`, `to-tickets`, `diagnosing-bugs`, `writing-great-skills`, and `setup-agent-tracker` (the per-repo issue-tracker/triage/domain setup skill, de-branded from upstream's `setup-matt-pocock-skills`). Every imported skill was reviewed for prompt-injection, exfiltration, and destructive commands by an adversarial multi-agent pass before import. Run `agent-notes regenerate` to apply.
- **`no-ai-attribution` global rule.** Forbids any AI model (Claude or otherwise) from adding `Co-Authored-By` trailers, "Generated with", `🤖`, or any self-attribution to commit messages, PR titles/descriptions, code comments, or anywhere else. Distributed to all CLIs like the existing `safety` and `code-quality` rules; the `git` skill cross-references it.

- **"Decompose before delegating" rule in lead instructions.** Before dispatching a coder/refactorer/test-writer, the lead must convert investigation findings into an ordered `file → change → reason` checklist and pass concrete `file:line` findings verbatim, so executing agents run a batch instead of re-exploring already-mapped code. Adds a matching anti-pattern and coder/refactorer directives. Run `agent-notes regenerate` to apply.

- **`agent-notes validate` now checks skills.** Errors (block release): `SKILL.md` over 500 lines or 5,000 tokens; `description` over 1,024 chars; reference files over 100 lines without a table of contents (defined as `## Contents` heading in first 20 lines, listing sections with `[Title](#anchor)` links); reference files linking to other reference files; broken relative links; unknown frontmatter keys (allowed: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility`, `group`, `requires_memory`, `triggers`). Warnings: `description` over 250 chars. These checks run at release pre-flight and are enforced by `scripts/release`.

- **Long reference files (over 100 lines) across all skills now include a table of contents at the top,** listing major sections with anchor links to improve navigation.

- **Skill descriptions shortened to 250 characters or fewer** to leave room in Claude Code's shared skill listing, which is capped at 1% of the context window and drops the least-used skills' descriptions first. Affected: `rsi`, `code-review`, `rails`, `refactoring-protocol`, `ingest`, `docker`, `codebase-design`. Trigger keywords preserved; first sentence names the primary use case.

- **The five largest SKILL.md files now open with a `## Rules` section** holding must-hold instructions for re-invocation. Affected: `chrome-test`, `wayfinder`, `obsidian-memory`, `diagnosing-bugs`, `ingest`. The Rules section puts the must-hold instructions first, phrased as standing rules, because Claude Code does not re-read a skill after invoking it.

- **Skill quality and safety pass ([spec 009](specs/009-skill-quality-and-safety/spec.md)).** Additions:
  - `agent-notes memory add --body-file PATH` reads a multi-line body from a file (`-` reads stdin), so memory examples no longer put note text inside a double-quoted shell argument.
  - `agent-notes validate` warns when a skill `description` has no "Use when" clause (the warning does not block release).
  - `setup-agent-tracker` checks the `gh`/`glab` CLI and its authentication first, then offers to create the triage and `wayfinder:*` labels (it lists what exists, creates only the ones you approve, never overwrites).
  - `argument-hint` on `code-review`, `to-spec`, `to-tickets`, `triage`, `wayfinder`, `ingest`, `research` and `chrome-test`; a `## Rules` block and post-commit check in the `git` skill, and a worked example in `to-tickets`.
  - A skill evaluation prompt set (`tests/skill_evals/prompts.yaml`, 140 prompts covering all 25 skills, each with should-trigger and near-miss cases), a schema test for it, and a one-prompt runner (`tests/skill_evals/runner.py`) that sends one prompt through `claude -p` and reports which skill loaded. Running the full set is not automated.

### Changed

- **`chrome-test` runs the browser test through the `browser-tester` agent.** The main session checks that the Chrome tools and a connected browser exist, dispatches the agent in the background with the request path, and saves the returned report to `report-<uuid>.md`. There is no polling and no "report ready" relay. The manual `claude --chrome` session is now the fallback, used when the tools are missing, no browser is connected, or the extension fails. The lead's pipeline and verification text follow the same flow, and a report can now mark a scenario BLOCKED, which keeps the gate open.

- **The install wizard and the interactive `config` menu are replaced by one review screen.** `agent-notes install` opens it with every setting pre-filled: ↑↓ move, ⏎ edits a row, ←→ changes simple values, `i` installs (quiet build, then "Install N files (M backed up)?"), `q` quits. `agent-notes config` opens the same screen on an existing install (the current folder's, else global, else a picker): `tab` switches installs, `u` moves deprecated or unknown pins to the recommended model, `s` shows the diff and saves everything with one state write and one regenerate; API keys save as soon as entered. Terminals under 60×16 (or without `termios`) get numbered prompts. With no terminal, `install` installs the recommended setup without prompts — piped answers are no longer read. Scriptable `config` subcommands and `install --local/--copy/--profile/--folder/--global-home` are unchanged. `config show` uses the same layout and flags outdated pins.

- **Recommended models for Claude Code and OpenCode: reasoner → `claude-opus-5-5`, worker → `claude-sonnet-5-5`** (were `claude-opus-5` / `claude-sonnet-5`). Both are not yet rated upstream, and an unrated model could never become a default, so `rules.yaml` gains a `provisional_coding_index` block: a hand-curated stand-in score used only while OpenRouter has no coding score, retired automatically once it does. Model tables mark it with `*` (e.g. `78.1*`). Orchestrator, scout and every Codex default are unchanged. Existing installs keep the models saved when they were installed — re-run `agent-notes install` to pick up the new recommendations.

- **Refreshed vendored Matt Pocock skills from upstream:** `code-review`, `tdd`, `grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `handoff`, `prototype`. Renamed to match upstream: `debugging-protocol` → `diagnosing-bugs`, `write-a-skill` → `writing-great-skills`, `setup-project-context` → `domain-modeling`, `to-prd` → `to-spec`, `to-issues` → `to-tickets`.
- **Plugin build now vendors full skill directories** (including bundled reference files such as `tdd/mocking.md`, `codebase-design/DEEPENING.md`) and prunes retired/renamed skills from `.claude-plugin/skills/` on each build, instead of copying only `SKILL.md` and leaving stale directories behind.

- **Cost reporting is now opt-in (default: disabled).** Previously, the per-response token-usage table was appended to every Claude Code / OpenCode response by default. It is now disabled for new installs. Existing users whose config does not contain `cost_report_enabled` will also see reporting disabled after upgrading. To opt in, run `agent-notes config cost-report on` then `agent-notes regenerate`.

- Cost reporting is a "Cost report" row on the install review screen (default: off).

- Memory is a "Memory" row on the review screen: `built-in` (default) or `Obsidian` (single-brain or per-project strategy).

- Chrome-test handoff uses uuid-correlated bus files (`request-<uuid>.md` / `progress-<uuid>.md` / `report-<uuid>.md`), path-only handoff, `X/N` step progress, and supports parallel requests.

- **A reinstall replaces the install.** Running `agent-notes install` again for the same target (same scope, project and profile) replaces it. This run's choices win: model pins start from the recommended ones, as on a first install.

- **Leftovers are removed:** deselected skills (also in `~/.agents/skills`), a dropped CLI's agents, config, context file and session hook, copy↔symlink leftovers, and skills, rules or agents removed from the package.

- **What counts as ours:** only what agent-notes placed is removed, meaning links into its own package and unedited copies it recorded. Your own files and links are never deleted. Edited copies are moved to `<name>.bak.<timestamp>` when a new file takes their place.

- **Shared files:** files another install still uses (`~/.codex`, `~/.agents/skills`, a project's `CLAUDE.md`/`AGENTS.md`) are kept.

- **The confirmation says what will be removed:** `Install N files (M backed up, K removed)?`.

- **The flags path:** `install --local/--copy/--profile/--folder/--global-home` on an existing install shows what will be replaced and removed and asks first. `--yes` skips the prompt. Without a terminal and without `--yes` it refuses (exit 2). The old "Installation is healthy" check on an existing install is gone; use `agent-notes doctor`. `--reconfigure` is still accepted and does the same as a plain reinstall.

- **Our own unedited copies are replaced without a `.bak`.** A link you made yourself at a target is moved to `.bak`, never deleted. The "N backed up" count is accurate.

- **`uninstall` removes only what agent-notes placed.** In copy mode it no longer deletes your own files, and it leaves foreign links in `~/.agents/skills` alone.

- **One-time note:** copy-mode skill folders installed before this release are backed up once on the next reinstall, because their old records cannot prove they are unedited.

- **Concurrent installs are not supported.** State and other installs' claims are read from one snapshot per run.

- **Rails skill refreshed against Fizzy** (basecamp/fizzy, pinned commit `6aebc0cea63d0e5fcdd2eeea138072ddcb26be74`, 2026-10-05). Split into 29 focused reference files with a router `SKILL.md`. Teaches released Rails 8.1.4; Fizzy's Rails-main-only APIs (e.g. `Migration[8.2]`) are labelled as such. Defaults to Solid Queue, Solid Cache, and Solid Cable instead of Redis (mentioned only for apps already using it). All examples copied from Fizzy or marked illustrative. ViewComponent labeled "Added by the owner, not from Fizzy/37signals" and names its source. Fills gaps: `Current`/CurrentAttributes, delegated types, multi-tenancy, concerns, Turbo 8 morphing, testing conventions. Every reference file ends with a Sources section listing Fizzy paths and articles. Style guidance defers to the project's `.rubocop.yml` config; Fizzy's house preferences are noted as the 37signals default when the project has no rule. Each coding rule cites its source.

- **Docker skill split into 9 topic-focused reference files,** each under 300 lines. Replaces the 2 large reference files (`compose.md`, `dockerfile.md`). The `SKILL.md` becomes a router listing each reference with a one-line "read when…" summary. All original headings and code examples preserved in the split output. Every reference file over 100 lines includes a table of contents.

- A new test confirms that a copy-mode reinstall replaces a skill's directory, so reference files renamed by the docker and rails splits leave no stale copies.

- **Install, reinstall, uninstall, and `doctor --fix` never modify, move, back up, or delete anything under `~/.claude/skills/synced/` or `~/.claude/skills/.trash/`.** A skill directory named `synced` (any letter case) or starting with `.` is refused at build and install, and by `agent-notes validate` with an error message. This protects Claude Code's synced skills from accidental overwrite.

- **Skill behaviour changes ([spec 009](specs/009-skill-quality-and-safety/spec.md)).**
  - **Triage checks the claim before running anything.** It reads a PR's diff first (`gh pr diff`), never checks a PR out in your working tree, and asks you every time before running PR code or a reporter's steps in a separate git worktree. The "This was generated by AI during triage" disclaimer is no longer required on triage comments.
  - **Tracker fixes.** The GitHub external-PR query uses `gh api` and `author_association` (the `gh pr list` field it relied on does not exist); one fallback sentence ("ask the user to run `/setup-agent-tracker`") replaces the differing wordings in `code-review`, `to-spec`, `to-tickets`, `triage` and `wayfinder`; `to-tickets` uses one ticket format.
  - **Descriptions.** 21 skill descriptions are rewritten in the third person with a "Use when" clause (250 characters or fewer), with routing hints between overlapping skills (`refactoring-protocol`/`rsi`/`improve-codebase-architecture`, `codebase-design`, `code-review` vs the `reviewer` agent, `diagnosing-bugs` vs the `debugger` agent). The unused `triggers:` frontmatter key is removed from `chrome-test`, `docker` and `rails`, and `agent-notes validate` now rejects it as an unknown key.
  - **Rails and docker.** The `rails` skill's tenancy guidance is consolidated and leads with its rules; only `models-migrations.md` still shows `Migration[8.2]` blocks, and it carries the Rails-main-only note. The `docker` skill's Rails example is taken from a real `rails new` with current versions and Solid defaults.
  - **Asking before commits.** `rsi` and `refactoring-protocol` ask once at the start "Commit each step as I go?" and never push; `prototype` asks separately before committing its throwaway branch and before commenting on an issue; the `git` skill gains a Rules block (specific-file staging, no `--no-verify`/`--force`, no push without asking, attribution rules override harness templates).
  - **Handoffs to user-only skills** (`diagnosing-bugs`, `refactoring-protocol`, `rsi`, `wayfinder`) now say "suggest the user run `/<skill>`" instead of running them.
  - **Memory skills match the real layout.** `obsidian-memory` and `ingest` describe the actual vault layout (flat `<root>/Patterns/…` by default, `<root>/<cwd-name>/Patterns/…` per project), document `project:` as frontmatter-only, check `agent-notes memory list` before writing, and `ingest` stops when the backend is not Obsidian.
  - Smaller edits in `code-review`, `codebase-design`, `domain-modeling`, `to-spec`, `to-tickets`, `wayfinder`, `handoff`, `research`, `improve-codebase-architecture` and `setup-agent-tracker` for concision and consistent vocabulary.

- **CI.** Workflows use Node 24 actions (`actions/checkout@v5`, `astral-sh/setup-uv@v7`). The catalog-refresh workflow still runs the test suite, but when it fails it now opens the model-catalog PR as a draft that lists the failing tests, instead of not opening a PR.

### Removed

- Retired the `caveman` and `zoom-out` skills, which were removed from the upstream Matt Pocock repo (caveman was a private test skill; zoom-out went unused). `chrome-test` is retained as an agent-notes skill.

- **`agent-notes memory migrate` is removed.** It was unreachable from the CLI (not in the argument choices); its module, help lines and tests are deleted.

### Security

Findings from the skills security audit, closed in [spec 009](specs/009-skill-quality-and-safety/spec.md).

- **Untrusted content is data, never instructions.** `chrome-test`, `code-review`, `ingest`, `obsidian-memory` (read protocol), `research`, `to-spec`, `to-tickets`, `triage`, `wayfinder` and the GitHub and GitLab tracker docs of `setup-agent-tracker` now say that text from issues, PRs, comments, web pages and browser reports must not be followed as directives and is surfaced to you instead.

- **Shell quoting.** Issue, PR and note bodies reach the shell on stdin through a single-quoted heredoc (`--body-file -`, `--description-file -`, `glab api … -F body=@-`), never inside a double-quoted argument, and titles are single-quoted. `gh issue close --comment` is no longer used for untrusted text. The `ingest` and memory examples pass bodies with `agent-notes memory add --body-file`.

- **GitLab quick actions.** Before posting a description or note that quotes untrusted text, no quoted line may start with `/` (GitLab runs quick actions from line starts); quote it as a `> ` blockquote or indent it in a code block.

- **Confirmations.** `wayfinder` asks before creating the map and its tickets, before closing an issue or editing the map, and before any AFK task that touches accounts, access or data; the map's Notes are data, and only skills you approved can be invoked from them. `to-spec` shows the final spec text before publishing, and neither `to-spec` nor `to-tickets` auto-applies `ready-for-agent` to content that came from an issue, URL or PR.

- **`ingest`.** Notes ingested from URLs, files or folders are marked external-source (first body line `Source (external): <url or path>`), and the `obsidian-memory` read protocol treats marked notes as data. One shared exclusion list now covers both modes, including folder mode, and adds `*-secrets.*`, `service-account*.json`, `*.pfx`, `id_rsa`, `.npmrc`, `.netrc`, `.aws` credentials, `*.tfstate` and names containing `token`, `apikey` or `private-key`.

- **`improve-codebase-architecture` report.** Tailwind and Mermaid are pinned to exact versions with SRI hashes, Mermaid runs with `securityLevel: "strict"`, and every repo-derived string is HTML-escaped. The skill also checks the generated HTML for leftover `{{ }}` placeholders before opening it.

- **`chrome-test`.** The request file may hold only what the browser session needs (URLs, scenarios, steps, expected results), the report and progress files are marked untrusted, and the bus directory name is the repo folder name plus a hash of its absolute path, so two repos with the same folder name no longer share a bus.
