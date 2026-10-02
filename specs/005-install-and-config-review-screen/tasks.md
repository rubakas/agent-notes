# 005 — Install and Config Review Screen: Tasks

Ticket index for `plan.md`, which holds the code, tests and commands for each one. Every ticket is test-first and ends green. Each phase can merge on its own.

## Phase A — TUI foundation (no behavior change)

- [ ] **T01 Key input** — `services/tui/keys.py`: arrows, timed Esc, UTF-8, cbreak mode restored on Ctrl-C. FR-021, SC-006. Review Focus 2, 5.
- [ ] **T02 Screen helpers** — `services/tui/screen.py`: `Style`, `fit`, `tilde`, `elide_middle`, `Terminal`; `NO_COLOR` honoured in `services/ui.py` too. FR-022, FR-023, SC-008.
- [ ] **T03 Review form** — `Row`, `ReviewForm`: cursor, ←→ cycle, ⏎ edit, commands, Esc semantics, width-safe render. FR-004, FR-021, FR-023. Review Focus 3.
- [ ] **T04 Picker** — scrolling, tags, dimmed rows, cursor on the current value. FR-008.
- [ ] **T05 Checklist, text field, path completion** — validation on a second ⏎, secret input never rendered. FR-010–FR-013, FR-018. Review Focus 5.
- [ ] **T06 Sessions** — `TuiSession`, `LineSession`, `open_session` (60×16 floor, no termios, no TTY). FR-025, FR-026. Review Focus 2.

## Phase B — `agent-notes install`

- [ ] **T07 Role models** — `Catalog`, ★ = resolver pick, three-check effort options, Models editor. FR-007–FR-009, SC-003, SC-004.
- [ ] **T08 Review rows** — `InstallChoices`, initial values, rows from the capability registry, memory/toggle/profile/skills editors. FR-002, FR-003, FR-010–FR-013.
- [ ] **T09 Switch install over** — new orchestrator (quiet build, inline confirm, restore on decline, no-TTY path); delete the step flow, selectors and 12 obsolete test files; migrate surviving behaviors. FR-001, FR-005, FR-006, FR-024, FR-026, FR-027, SC-001.
- [ ] **T10 Wording and pty check** — `built-in` / `Obsidian` in the post-install summary; end-to-end pty test. FR-028, SC-001, SC-002, SC-009.

## Phase C — `agent-notes config`

- [ ] **T11 Install discovery** — `InstallRef`, `list_installs`, `default_install`; missing folders never chosen. FR-014, SC-005. Review Focus 4.
- [ ] **T12 Config rows** — flagged pins (⚠ deprecated / unknown, ★ hint), `u`, memory, toggles, API keys, read-only line. FR-015, FR-016, FR-018. Review Focus 1.
- [ ] **T13 Config session** — staged edits, one save and one regenerate of the edited install, safe quit, Tab, no-TTY; numbered menu deleted. FR-014, FR-017, FR-019, SC-007; spec Corrections 2–3.
- [ ] **T14 `config show`** — static review layout, shared settings once, each install after. FR-020.

## Close

- [ ] **T15 Docs and verification** — README, CHANGELOG, measured SC-001–SC-010 and mutation checks recorded in `spec.md`. FR-029, SC-010.
