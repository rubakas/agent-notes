# 005 — Install and Config Review Screen

**Feature Branch**: `feat/install-config-review-screen` (to be cut after spec 004 lands — this spec uses 004's `rank_score` and provisional `*` marker)

**Created**: 2026-10-02

**Status**: Implemented 2026-10-02

**Input**: User description: "make installation and config processes more useful for human, easier to select options and more visually better and compact design"

## Investigation

The real install wizard was driven in a pty (pexpect, 100×32, sandboxed `HOME`, working-tree binary, every default taken, `n` at the final prompt) and its screens captured verbatim on 2026-10-02. `agent-notes config` was captured the same way against a sandbox copy of the owner's `state.json`.

**Install — 16 screens to accept every default.** 9 numbered steps (`orchestrator.py:67-136`, step count from `capabilities._compute_total_steps`):

- "Step 2 of 9" alone spans 7 screens: the accept-all gate, then per role a 15-row model list and a separate 5-row effort list (`wizard/__init__.py::_select_models_per_role`). The model list includes 6 deprecated and 2 over-budget models with no marker for the recommended pick; the effort screen repeats the whole model row (`for claude-opus-5-5  57.6  78.1*  4.00 (via anthropic)`).
- Install mode, profile and cost report each take a full screen for a two-way choice almost everyone leaves at the default.
- The first chance to review is a `Proceed? [Y/n]` text prompt after a build (`_confirm_install`, `wizard/__init__.py:538-575`); there is no way back to change a choice.
- The build log (`Generating agent files... Copying skills...`) prints mid-wizard, and again after a cancel (`_restore_persisted_render`).
- Wording drifts: memory is "default — the CLI's native memory / Claude Code built-in md files" on its screen and "Local markdown" on the next; the skills screen shows `Codebase-design — codebase-design` (a hard-coded description dict, `_select_skills`, falls back to the id).
- The welcome text ("Includes 56 agents…") is printed and cleared by the next screen before it can be read.

**Config — a different, weaker interface.** `interactive_config` (`config.py:721`) prints a 7-item numbered menu, reads typed role names and indices, makes one change, regenerates and exits.

- It cannot find the owner's installs: `_get_scope_state` (`config.py:24`) picks global, else the *current folder's* local install. The owner has only local installs, so `agent-notes config` run from any other folder exits 1 with "No local installation found".
- Menu items 2 ("Role → agent assignments", `role_agent`) and 4 ("Skill bundles", `_wizard_skills`) are dead ends that only print instructions.
- Both installs pin `claude-opus-4-6`, which is deprecated; nothing says so.

**Shared widget defects** (`services/ui.py`):

- Esc *confirms* the highlighted option in every selector (`_checkbox_select:252`, `_radio_select:352`).
- A bare Esc hangs: `_read_key` (`ui.py:177-196`) reads two more bytes after `\x1b`, so the key registers only after two further keypresses.
- `NO_COLOR` is ignored; color is disabled only when stdout is not a TTY (`ui.py:45`).
- Each selector carries two full renderers (stepped and "legacy in-place") plus a numbered fallback.

**Test coupling.** 19 test files drive the step functions or selectors directly — 17 unit (`tests/unit/commands/test_wizard_*.py`, `wizard/test_cost_report_step.py`, `test_toggle_capabilities.py`, `test_config_role_model_index.py`) and 2 functional (`tests/functional/commands/test_wizard_happy_path.py`, `test_config_command.py`). Across the tests, `_radio_select` appears 49 times, `_confirm_install` 36, `_select_models_per_role` 27.

## Decisions (owner, 2026-10-02)

| Question | Decision | Rejected |
|---|---|---|
| Priorities | All four: fewer screens, easier model choice, better config, polish | — |
| Overall shape | One review screen, every setting pre-filled; edit any row; shared by install and config | Shorter linear wizard; Quick/Custom fork |
| Model picker | Full list, annotated (★ recommended, over-budget tag, deprecated dimmed) | Short list with the rest folded behind `a` |
| Dependencies | None added — extend the existing raw-key/ANSI approach | prompt_toolkit; rich |
| Sections 1–4 of the design | Approved as presented in chat | — |

## Corrections after approval (2026-10-02)

Found while writing the implementation plan; each keeps today's behavior where the approved text assumed otherwise.

1. **Install flags do not pre-fill the review.** `cli.py:349-356` routes `install --local / --copy / --profile / --folder / --global-home` to the non-interactive `commands.install.install()`; only a bare `install` (or `install --reconfigure` alone) reaches the wizard. The approved FR-003 clause and Story 1 scenario 4 assumed the flags pre-set the review. They do not, and changing that would break scripted `install --local`. Kept as is; FR-003, Story 1 scenario 4 and the `--reconfigure` edge case are corrected above.
2. **API keys save when entered.** They live in the credentials file, outside `state.json` and regenerate, as today (`_wizard_providers`). The API-keys editor writes a key as soon as it is entered and is not part of the staged edits FR-017 counts. The optional `base_url` prompt that follows a key today is kept.
3. **Config regenerates the install it edits.** Today's `_apply_and_regenerate` calls `regenerate()` with no arguments, which auto-detects global-else-cwd — the wrong install when the edited one is a local install elsewhere. The config save passes the edited install's scope, project path and profile label.
4. **`_confirm_install` and `_render_install_summary` are removed** — the review screen and the inline confirmation replace them. `_format_role_model_display` stays: the post-install summary (`execute._render_configuration`) uses it.
5. **Esc on an editor form keeps what was changed in it.** The Models table, the Obsidian editor and the Profile editor are forms whose changes apply as you make them; Esc closes the form and keeps them. Esc in a picker, a checklist or a text field cancels that one edit with no change.
6. **Line-mode yes/no questions re-ask on an unclear answer, and discarding defaults to No.** An answer other than y/yes/n/no (any case) prints "please answer y or n" and asks again; an empty answer takes the question's default — yes for "Apply N changes?" and the install question, No for "Discard N changes?" (`[y/N]`). The full screen is unchanged: ⏎ yes, Esc no.
7. **`q` at the install confirmation quits.** It restores `dist/` as any non-yes does, then exits with "Installation cancelled.", like `q` on the review screen (a failed restore stays on the review so the regenerate instruction is seen); the footer reads `⏎ yes · esc back · q quit`, and line mode asks `[Y/n/q]`. Config's "Apply N changes?" and "Discard N changes?" prompts read `q` as no, never as a discard.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install with the recommended setup in two keypresses (Priority: P1)

A user runs `agent-notes install`, sees every setting already filled in on one screen, presses `i`, sees how many files will be written, and presses ⏎.

**Why this priority**: P1 — it is the path almost every install takes, and today it costs 16 screens.

**Independent Test**: In a pty at 80×24, `agent-notes install` followed by `i` and ⏎ installs with the recommended values; the capture contains one review screen and one confirmation line, no step screens, and no build log lines.

**Acceptance Scenarios**:

1. **Given** a fresh machine, **When** `agent-notes install` opens, **Then** the first screen is the review screen with recommended values in every row.
2. **Given** the review screen, **When** the user presses `i`, **Then** the build runs with one progress line and the screen shows `Install N files (M backed up)? ⏎ yes · esc back · q quit`.
3. **Given** that confirmation, **When** the user presses Esc, **Then** nothing is written, the persisted render is restored silently, and the review screen returns with every edit intact.
4. **Given** `agent-notes install --local --copy` (or `--profile`, `--folder`, `--global-home`), **When** it runs, **Then** it installs non-interactively exactly as today — those flags route to `commands.install.install()` and never open the review (see Corrections).

### User Story 2 - Choose a model and effort per role with the facts in view (Priority: P1)

A user wants a different model for one role. They open Models, change one role's effort with ←→, open its model list, and see which model is recommended, which are over the role's budget, and which are deprecated.

**Why this priority**: P1 — model choice is the step with the most screens and the least guidance today.

**Independent Test**: For every backend × role, the ★ in the picker equals `select_model_for_role`; the effort values offered equal the three-check set.

**Acceptance Scenarios**:

1. **Given** the Models table, **When** the user presses ←→ on a role, **Then** the effort cycles through exactly the values that role's model, provider and CLI all accept.
2. **Given** the model picker for Reasoner on Claude Code, **When** it opens, **Then** the title shows `budget $5/M in`, `claude-opus-5-5` carries ★, `claude-fable-5-1` carries `over budget`, deprecated rows are dimmed and tagged, and every row is selectable.
3. **Given** a picked model without effort support, **When** the table redraws, **Then** that role's effort shows `—` and none is saved.
4. **Given** a role changed away from its recommendation, **When** the user presses `r`, **Then** model and effort return to the recommended values.

### User Story 3 - Review and change an existing install with `config` (Priority: P2)

A user runs `agent-notes config` from any folder. It opens their install on the same review screen, flags the deprecated pin, and lets them fix several things before saving once.

**Why this priority**: P2 — config is used less often than install, but today it fails outright for the owner.

**Independent Test**: With only local installs in state and the current folder not one of them, `agent-notes config` lists the installs to pick from instead of exiting 1.

**Acceptance Scenarios**:

1. **Given** the current folder has a local install, **When** `config` opens, **Then** it shows that install; otherwise the global install; otherwise a list of all installs to pick from.
2. **Given** a role pinned to a deprecated model, **When** config opens, **Then** that row shows `⚠ deprecated` and the ★ recommendation, and `u` replaces every ⚠ pin with its ★ model.
3. **Given** three staged edits, **When** the user presses `s` and ⏎, **Then** the diff is shown, state is written once and regenerate runs once.
4. **Given** staged edits, **When** the user presses `q`, **Then** they are asked whether to discard them.

### User Story 4 - Consistent, quiet, compact screens (Priority: P3)

Every interactive screen uses one header, one footer, one vocabulary and one meaning for Esc.

**Why this priority**: P3 — polish across all of the above; each item is small, together they are the "looks better" request.

**Independent Test**: Widget tests press Esc in every widget and assert it never confirms; a `NO_COLOR=1` run emits no color codes; no line rendered at 80 columns is wider than 80.

**Acceptance Scenarios**:

1. **Given** any editor, **When** the user presses Esc once, **Then** it returns to the previous screen without changes, immediately.
2. **Given** `NO_COLOR=1`, **When** any screen renders, **Then** it contains no ANSI color sequences.
3. **Given** a path longer than the space for it, **When** it renders, **Then** home is shown as `~` and the middle is elided; the line does not wrap.

### Edge Cases

- No CLI selected: `i` is refused with `select at least one CLI` on the footer line.
- Several CLIs selected: Models shows one block per CLI that supports agents; config-only CLIs have no block.
- A CLI with no compatible models: its block reads `no compatible models — uses legacy tier resolution` (today's warning, kept) and is not editable.
- `install --reconfigure` with no other flag: opens the review, as it opens the wizard today (the flag is only acted on by the non-interactive `install()` path).
- Profile label left empty: profile stays default; folder and home fields are ignored.
- Obsidian path that is not a vault: an inline warning; the user may keep it (today's behavior).
- Terminal resized while open: the next keypress redraws at the new size.
- Terminal smaller than 60×16, or `termios` unavailable (Windows): line mode — see FR-025.
- stdin or stdout not a TTY: no prompts — see FR-026.
- `config` with no installs at all: `No installation found — run agent-notes install`, exit 1.
- Credential values: never rendered, logged, or echoed on any screen; API keys shows only ✓ / —.

## Requirements *(mandatory)*

### Install review screen

- **FR-001**: `agent-notes install` on a TTY MUST open the review screen directly. The 9-step flow, the step counter and the accept-all gate are removed.
- **FR-002**: Rows, in order: CLIs, Models, Scope, Install as, Skills, Memory, one row per registered toggle capability (by `order`), Profile. CLIs, Models, Memory and toggle rows come from the capability registry (FR-027); the rest are fixed.
- **FR-003**: Initial values: CLIs `{claude}`; per role the model `select_model_for_role` picks and the effort `_effort_default_choice` picks; Scope `global`; Install as `symlink`; all domain skills; Memory built-in; each toggle at its capability default; Profile default. (The install flags never reach the review — see Corrections.)
- **FR-004**: Review keys: ↑↓ move between rows (the Models block is one row per CLI); ←→ cycle a row's value where the row is a cycle (Scope, Install as, Memory, toggles); ⏎ opens the row's editor (CLIs, Models, Skills, Memory when Obsidian, Profile); `i` install; `q` quit without writing. Esc on the top-level review does nothing.
- **FR-005**: `i` MUST build with output suppressed and one progress line, then show one confirmation line with the planned file count and backup count (backed-up paths listed beneath, at most 5, then `… N more`). ⏎ runs the existing `_execute_install`; Esc restores the persisted render silently and returns to the review with every value intact.
- **FR-006**: The header shows `AgentNotes <version> · install` on the left and agent/skill/rule counts on the right; it replaces the separate welcome screen.

### Editors

- **FR-007**: Models role table, per CLI: one row per role (Claude Code still omits `orchestrator`); columns role, model, ★ when it is the recommended model, effort, `$/M in`. ←→ cycles effort (FR-009); ⏎ opens the model picker; `r` resets the role's model and effort to recommended; Esc returns.
- **FR-008**: Model picker: every model `compatible_models_for(backend)` returns, in registry order. Columns: id, ★, intelligence, coding (as `model_columns` renders it, including the provisional `*`), `$/M in`, and a tag — `over budget` when the role has a budget and `price_in` exceeds it, `deprecated` when the model is deprecated (row dimmed). The title is `<Role> · <CLI> · budget $X/M in` (`unbounded` when the budget is null). The cursor starts on the current model; the list scrolls inside the screen. Every row is selectable.
- **FR-009**: The effort values offered for a role MUST be exactly those that pass all three checks `config role-effort` applies: the model's `effort_support`, the provider's effort vocabulary, and the CLI's subset when it declares one. Picking a model without effort support clears the role's effort (shown `—`, not saved); picking a model whose allowed set excludes the current effort resets it to `_effort_default_choice`.
- **FR-010**: CLIs editor: a checklist of `cli_registry.available()`; space toggles, ⏎ finishes. Adding a CLI fills its Models block with recommended values; removing one drops its block.
- **FR-011**: Skills editor: a checklist of domain skills; each label is the skill name plus the first sentence of its `SKILL.md` frontmatter `description`, truncated to fit. `a` toggles all; process skills show as one fixed line `process (N) — always included`. The hard-coded description dict in `_select_skills` is removed.
- **FR-012**: Memory: ←→ cycles `built-in` / `Obsidian`. With Obsidian, ⏎ opens a strategy cycle (`single-brain` / `per-project`) and a vault-path text field with detected vaults listed, Tab completion, and an inline warning when the folder is not a vault (keeping it is allowed).
- **FR-013**: Profile: ⏎ opens three text fields — label, local folder, global home — with folder and home pre-filled from the label (`.claude-<label>`, `~/.claude-<label>`) until edited.

### Config

- **FR-014**: `agent-notes config` (no action) on a TTY opens the review screen in config mode, header `AgentNotes <version> · config` with the install's scope and path on the right. Install choice: the current folder's local install, else global, else a picker listing every install. Tab cycles installs when there is more than one. With no installs: `No installation found — run agent-notes install`, exit 1.
- **FR-015**: Editable rows: Models (FR-007 – FR-009), Memory (FR-012), toggle rows, API keys. CLIs, Scope, Install as, Skills and Profile show as one dimmed line with `change with: agent-notes install --reconfigure`.
- **FR-016**: A role pinned to a deprecated model shows `⚠ deprecated` and the ★ recommended id; a pin that differs from the recommendation but is not deprecated shows only the ★ id as a hint. `u` sets every ⚠ role to its recommended model and the effort `_effort_default_choice` picks for it, as staged edits.
- **FR-017**: Edits are staged; the footer shows the count. `s` shows the diff (`<cli> <role>: <old> → <new>`, one line per change) and ⏎ applies all of them through one state write and one `_apply_and_regenerate`; Esc returns with edits kept. `q` with staged edits asks `discard N changes? y/n`.
- **FR-018**: API keys: one line per provider with `✓` (key stored) or `—`; ⏎ on a provider asks for a new key with hidden input (no echo); empty input changes nothing. Key values MUST NOT be rendered, logged or printed anywhere.
- **FR-019**: The interactive menu items "Role → agent assignments" and "Skill bundles" are removed. Every scriptable subcommand (`show`, `role-model`, `role-agent`, `role-effort`, `provider`, `providers`, `memory`, `cost-report`) keeps its current arguments and behavior, except `show`'s layout (FR-020).
- **FR-020**: `config show` prints the config-mode review layout statically (no cursor, no footer) for every install in state, including ⚠ flags.

### Cross-cutting

- **FR-021**: Esc MUST mean back/cancel in every editor and picker and MUST never confirm. A bare Esc is recognized without waiting for further keys: after `\x1b`, the reader waits at most 50 ms (`select`) for a following byte before returning `escape`.
- **FR-022**: Color is disabled when stdout is not a TTY (as today) or when `NO_COLOR` is set to any non-empty value. Color is used only for role labels, ★, ⚠, tags and the cursor; secondary text is dim.
- **FR-023**: No rendered line may exceed the terminal width. Paths render with the home directory as `~` and are elided in the middle to fit.
- **FR-024**: Interactive flows MUST NOT print build or regenerate output; they show one progress line instead. The restore after a cancel prints nothing.
- **FR-025**: Line mode — when stdin and stdout are TTYs but the terminal is smaller than 60×16, or `termios` is unavailable: the review prints its rows numbered and asks `Change which? (number, enter to install, q to quit)`. Editors reuse the existing numbered pickers `_radio_select_fallback` and `_checkbox_select_fallback` and `_safe_input`. Config uses the same line mode in place of the old 7-item menu.
- **FR-026**: When stdin or stdout is not a TTY: `install` uses the FR-003 initial values with no prompts and prints the post-install summary; interactive `config` prints `config show` and the list of scriptable subcommands.
- **FR-027**: `CapabilityBehaviour` replaces `view` / `config_view` with `row` (install) and `config_row` (config, optional — a capability without one is not editable in config). `register` MUST reject a capability with no `row`. `_compute_total_steps` and every `step` / `total` parameter are removed.
- **FR-028**: Memory is named `built-in` or `Obsidian` on the review, the confirmation, config, `config show` and the post-install summary.
- **FR-029**: `pyproject.toml` runtime dependencies are unchanged.

### Architecture

- `agent_notes/services/tui/keys.py` — the key reader (↑↓←→, Tab, space, ⏎, Esc with timeout, Ctrl-C), and a key-source interface so tests can inject key sequences.
- `agent_notes/services/tui/screen.py` — terminal size, paint a list of lines (clear + write), text fitting and path elision, color gating.
- `agent_notes/services/tui/widgets.py` — `ReviewForm`, `TablePicker`, `Checklist`, `TextField`. Each is state plus `render(width, height) -> list[str]` and `handle(key) -> Action`; none touches the terminal.
- `agent_notes/commands/wizard/review.py` — builds the install rows from the capability registry and fixed rows; the orchestrator becomes initial values → review → build → confirm → `_execute_install`.
- `agent_notes/commands/config.py` — the interactive path builds config-mode rows and a save action on the same `ReviewForm`; install selection per FR-014.
- `services/ui.py` keeps `Color`, the status helpers (`ok`, `warn`, …), `_safe_input`, `_path_input` and the two numbered fallbacks; `_checkbox_select`, `_radio_select`, `_render_step_header` and `_render_nav_footer` are removed.

### Non-Goals

- Changing CLIs, Scope, Install as, Skills or Profile from `config` — they move files; `install --reconfigure` stays the way.
- Mouse input, and redrawing on resize before the next keypress.
- A full-screen mode on Windows (it gets line mode, FR-025).
- Redesigning the post-install summary beyond FR-028's wording.
- `uninstall`, `doctor`, `list` and the other commands.
- A real role→agent editor; `config role-agent` stays the existing informational no-op.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Installing with all recommended values takes one review screen and one confirmation line — two keypresses (`i`, ⏎) — measured by the same pty capture that counted 16 screens on 2026-10-02.
- **SC-002**: With one CLI selected, the review screen fits 80×24 and no rendered line at 80 columns is wider than 80, measured in the pty capture and by widget render tests.
- **SC-003**: For every backend × role, the picker's ★ equals `select_model_for_role` (test over the shipped catalog).
- **SC-004**: For every backend × role × compatible model, the effort values offered equal the three-check set (test over the shipped catalog).
- **SC-005**: With only local installs in state and the current folder not among them, `config` offers a picker instead of exiting 1 (test).
- **SC-006**: In every widget, Esc never confirms (key-sequence tests); a bare Esc returns `escape` within 100 ms (keys test with a fake fd).
- **SC-007**: Saving N staged config edits performs exactly one state write and one regenerate (test).
- **SC-008**: With `NO_COLOR=1`, no rendered screen contains an ANSI color sequence (test).
- **SC-009**: The interactive pty capture contains no build-log lines (`Generating agent files`, `Copying skills`).
- **SC-010**: `uv run pytest -q` is green; `pyproject.toml` dependencies are unchanged.

## Assumptions

- Spec 004 is merged first: the picker relies on `Model.rank_score`, the provisional `*`, and 004's new defaults.
- `select_model_for_role` stays the single source of "recommended"; the review never computes its own.
- The build-before-confirm order stays (`orchestrator.py:104-112`): the file count must come from the rendered `dist/`.
- `_execute_install`, `plan_install`, `_apply_and_regenerate` and the state store keep their current signatures; this spec changes how values are collected and shown, not how they are applied.
- Test churn is expected: the 19 step-function test files are rewritten against the widgets and the review rows; where a test guards a behavior that survives (profile re-render, preflight file count, build-before-confirm order, memory path validation, effort gating), the behavior keeps a test.
- Size: roughly 500–700 lines of widget and review code added, a similar amount of step-function and duplicate-renderer code removed — production code roughly flat; the cost is in tests.

## Verification

Measured 2026-10-02 on branch `feat/install-config-review-screen`, re-run after the final review's fix wave. All ten criteria are met.

| SC | Command | Result |
|---|---|---|
| SC-001 / SC-002 / SC-009 | `uv run --with pexpect pytest -q tests/functional/test_install_review_pty.py` | 1 passed — one review screen, `i` + ⏎ installs, no line over 80 columns, no build-log lines |
| SC-003 / SC-004 | `uv run pytest -q tests/unit/commands/test_review_role_models.py -k "star_is or effort_options_match"` | 2 passed, 16 deselected |
| SC-005 / SC-007 | `uv run pytest -q tests/unit/commands/test_config_review_installs.py tests/unit/commands/test_config_review_flow.py` | 26 passed |
| SC-006 | `uv run pytest -q tests/unit/tui/test_tui_keys.py tests/unit/tui/test_tui_review_form.py tests/unit/tui/test_tui_picker.py tests/unit/tui/test_tui_inputs.py -k "escape or esc"` | 7 passed, 45 deselected (includes the real-descriptor bare-Esc-under-100 ms test) |
| SC-008 | `uv run pytest -q tests/unit/tui/test_tui_screen.py -k no_color` | 3 passed, 12 deselected |
| SC-010 | `uv run pytest -q` | 2335 passed, 1 skipped, 15 deselected (baseline on develop @ 0ebf8c6: 2241 passed, 15 deselected) |
| SC-010 | `git diff 0ebf8c6 -- pyproject.toml` | empty — dependencies unchanged |

### Mutation checks

Each mutation was applied alone, the named test run, and the edit reverted at once (`git checkout -- agent_notes`; `git diff` afterwards showed no code change).

| Mutation | Result |
|---|---|
| `decode` reads two more bytes after ESC instead of checking `has_more` | `test_bare_escape_does_not_swallow_the_next_key` and `test_longer_csi_sequences_are_swallowed_whole` fail; the real-descriptor 100 ms test blocks on the read and was killed by a 60 s alarm (it cannot pass) |
| `ReviewForm.handle` returns DONE on ESCAPE always | `test_escape_does_nothing_on_the_top_level_review` fails |
| `effort_options` skips the CLI subset | `test_effort_options_match_the_config_role_effort_checks` and `test_codex_offers_only_the_efforts_the_cli_accepts` fail |
| config save calls `regenerate()` without arguments | `test_three_edits_save_with_one_write_and_one_regenerate` fails |
| `regenerate` places a local install's files without entering its project (the code before the fix wave) | `test_local_placement_runs_inside_the_project_not_the_cwd` and `test_saving_a_local_install_from_another_folder_places_files_in_that_project` fail: files placed from the calling folder |
