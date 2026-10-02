# 006 — Regenerate and Doctor Repair

**Feature Branch**: `develop` (direct; user instruction)

**Created**: 2026-10-03

**Status**: Approved 2026-10-03

**Input**: "fix found issues" (user, 2026-10-03), after a clean pipx reinstall on 2026-10-02 left 32 `~/.claude` links dangling.

## Investigation

A clean package install (on a fake `HOME` in a sandbox venv via pexpect, 2026-10-03) followed by a `pipx uninstall` + `reinstall` sequence reproduced the defect:

| Step | Total Links | Dangling |
|---|---|---|
| Fresh install | 50 | 0 |
| `pipx uninstall` + `install` (= venv deleted and recreated) | 50 | 50 |
| `regenerate --scope global` | 50 | 32 |
| `agent-notes build` | 50 | 0 |

After `regenerate --scope global`, 18 files were placed correctly (agents). The command printed "✓ rules regenerated / ✓ config regenerated / ✓ skills regenerated / Regenerated 55 files." and exited 0. Yet 32 links remained dangling: CLAUDE.md, 3 rules files, 3 commands, 25 skills.

Root cause: `dist/` is gitignored and not in the wheel (`pyproject.toml` package-data includes only `VERSION` and `data/**/*`); a fresh venv has no rendered files, so `regenerate` has nothing to copy.

## Defects (all reproduced)

**D1 — doctor crashes.** `services/diagnostics/_checks.py:36,159,212` use `from ... import installer`, which resolves to `agent_notes.installer` (does not exist; the module is `agent_notes.services.installer`). 9bb3fde (2026-07-29, #19) inlined `doctor_checks.py` into `_checks.py` and dropped `.services` from its `from .services import installer`; f056f75 had fixed the same mistake only in `_display.py:26,54`. Since then, `doctor` and `doctor --fix` crash at `check_stale_files` (first call is `commands/doctor.py:211,217`). `set_role.py:134` has the same error: `from ..regenerate` should be `from .regenerate`.

**D2 — regenerate never renders global files, rules, skills, or commands.** `commands/regenerate.py:109-160` only loops over agents with `generate_agent_files` (`:127`), then calls `installer.install_component_for_backend` for rules, config and skills (`:149,154,159`). Commands are never placed (no loop). On an empty `dist/` nothing is written.

**D3 — missing source is silent.** `install_executor.py:44-46` returns with no error when `dist_source_for` is None. `regenerate.py:150,155,160` print ✓ unconditionally, even when nothing was placed. `build.py:131-135` prints "Error" and returns exit 0 when the agents config is missing, so callers cannot detect failure.

**D4 — regenerate rewrites the install's CLIs.** `regenerate.py:178` calls `build_install_state` without `selected_clis`, so it records every backend with content in `dist/`. On an empty `dist/` the manifest shrinks (`claude` loses skills, rules, config; `opencode` is added if it has any `dist/` content). On a healthy `dist/` the install is widened with every backend present, and the next regenerate places files for them. This happened to the owner's `state.json` on 2026-10-02.

**D5 — wrong agent count.** `regenerate.py:136` counts agents with `backend.name in str(f)`, a substring over the full path. It printed "Regenerated 55 files" because the path contains "claude-501".

**D6 — dangling links reported as present.** `commands/_install_helpers.py:228` and `:244` count an item present if `Path(target).is_symlink()`, without following the link. A dangling link reads as "present". `install.py:62-63` downgrades a failed rebuild (exit non-zero) to a warning.

**D7 — test import gaps.** `tests/unit/test_import_health.py` checks only the module part of an import (for `from ... import installer`, `node.module` is None). It never verifies the imported name exists. Also scans only diagnostics files, so `set_role.py` is never checked. Every doctor test mocks `check_*` functions, and `set_role` has no test coverage.

## Functional Requirements

- **FR-001:** `doctor` and `doctor --fix` run every check without ImportError (D1).
- **FR-002:** `set role` completes and regenerates (D1).
- **FR-003:** `regenerate` runs the same full `build(scope, project_path, profile_label)` that `install` runs, before placing anything. After a fresh package install, `regenerate` alone leaves 0 dangling links (D2).
- **FR-004:** `regenerate` places every component type in `installer.COMPONENT_TYPES` (agents, rules, config, skills, commands). If `target_dir_for` is not None but `dist_source_for` is None, print an error and exit non-zero; a ✓ is printed only for what was placed (D2, D3).
- **FR-005:** `build()` raises on failure (structural or validation error), never prints and returns (D3).
- **FR-006:** `regenerate` keeps `state.clis` exact: it passes `selected_clis=set(scope_state.clis)` to `build_install_state` and never adds or drops a CLI (D4).
- **FR-007:** the agent count in `regenerate`'s output comes from the files placed, not a path-substring match (D5).
- **FR-008:** `_verify_install` counts an item present only if `Path(target).exists()` (follows symlinks); a failed rebuild is an error, not a warning (D6).
- **FR-009:** `test_import_health` verifies that every imported name resolves across all of `agent_notes/**/*.py`, with per-file anchors, collecting all failures in one assertion (D7).

## Success Criteria

- **SC-001:** the sandbox repro goes from 32 dangling to 0 with `regenerate` alone, after a fresh install.
- **SC-002:** `doctor` exits cleanly (code 0 or the expected error code) on a sandbox install.
- **SC-003:** every new test fails against the pre-fix code (verified by running against `git archive` of the pre-fix commit).
- **SC-004:** the full test suite stays green (`uv run pytest -q`).

## Out of Scope

- Reinstall cleanup, ownership, and per-profile render isolation (spec 007).
- Repairing the owner's `state.json` on 2026-10-02 (handled post-spec-007 with an interactive reinstall).
- Wizard post-install summary row wording.

---

## Tickets

Detailed task breakdown in `tasks.md`; each test-first, ends green.

| Ticket | Title | Requirements | Scope |
|---|---|---|---|
| **T01** | Import names | FR-001, FR-002, FR-009 | Fix `_checks.py` and `set_role.py` imports; extend `test_import_health`; new unit/functional tests for doctor and set_role |
| **T02** | Build fails loudly | FR-005 | `build.py:131-135` raises; audit callers |
| **T03** | Regenerate renders everything | FR-003, FR-004, FR-007 | Call `build()` once; loop over `COMPONENT_TYPES`; count placed files; new test on empty dist |
| **T04** | Regenerate keeps CLIs | FR-006 | Pass `selected_clis` to `build_install_state`; test manifest unchanged |
| **T05** | Truthful verify | FR-008 | Use `.exists()` in `_verify_install`; error on failed rebuild |
| **T06** | Verification and changelog | SC-001–SC-004 | Measure and record in `spec.md`; update CHANGELOG |

---

## Verification (2026-10-03)

- **SC-001:** pipx-like sandbox (non-editable venv built from the working tree, fake `HOME`).

  | Step | `.claude` links / dangling | `.agents` links / dangling |
  |---|---|---|
  | Fresh install | 50 / 0 | 25 / 0 |
  | Venv recreated | 50 / 50 | 25 / 25 |
  | `regenerate --scope global` alone | 50 / 0 | 25 / 0 |

  `regenerate` exited 0 and printed "Regenerated 50 files.".
- **SC-002:** `doctor` exit 0, "No issues found", 0 tracebacks.
- **SC-003:** the 22 new or changed tests all fail against `git archive HEAD` (pre-fix source).
- **SC-004:** `uv run pytest -q`: 2381 passed, 1 skipped, 15 deselected.
- State after `regenerate` stayed `claude{agents 18, skills 25, rules 3, config 1}`, and no `~/.config/opencode` was created.
