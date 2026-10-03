# Regenerate and Doctor Repair Implementation Plan

> **For agentic workers:** Use task-by-task execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix dangling-link defects and import errors introduced in #19 and discovered during reinstall testing.

**Baseline:** 2241 tests pass, 15 deselected. After Phase 1, Phase 2, Phase 3, each phase leaves the suite green and can merge on its own.

---

## Phase 1: Import and Build Errors

### T01 — Import names

**Files and changes:**

- `services/diagnostics/_checks.py:36, 159, 212`
  - Change: `from ...services import installer` → `from ...services import installer`
  - Reason: Module resolves to `agent_notes.services.installer`, not `agent_notes.installer` (fixed in f056f75 for _display.py only, D1)

- `commands/set_role.py:134`
  - Change: `from ..regenerate import regenerate` → `from .regenerate import regenerate`
  - Reason: Module is `commands.regenerate`, not `commands.set_role.regenerate` (D1)

- `tests/unit/test_import_health.py`
  - Change: Extend to scan all of `agent_notes/**/*.py` (not just diagnostics), verify imported names resolve, collect all failures in one assertion
  - Reason: Current check only verifies module name, not the imported name itself; misses set_role and other files (D7)

- New: `tests/unit/services/test_diagnostics_checks.py`
  - Change: Unmocked unit tests for `check_stale_files`, `expected_paths_for_install`, `_find_dist_source` on tmp dist
  - Reason: Current tests mock the checks; need to verify they run without import errors (FR-001)

- New: `tests/functional/commands/test_doctor_command.py` — unmocked `diagnose("global")` test
  - Reason: Functional coverage of doctor without mocked checks (FR-001, FR-002)

- New: `tests/unit/commands/test_set_role.py`
  - Reason: set_role has no test coverage (FR-002)

**Tests:** All pass. All new tests fail against pre-fix code.

---

### T02 — Build fails loudly

**Files and changes:**

- `build.py:131-135` (the error case when agents config is missing)
  - Change: Replace `print(...)` and `return` with `raise SystemExit(1)` or equivalent Exception
  - Reason: Callers check exit code; silent return is undetectable (D3, FR-005)

- `install.py:58-63` (rebuild after missing dist, during existing install)
  - Change: Audit how `install_component_for_backend` / `build()` failures are handled; if exit, let it propagate
  - Reason: Current code downgrades to warning (D6); rebuild failure should be fatal (FR-005)

- `install.py:75-79` (similar case during fresh install)
  - Change: Same audit; ensure failures propagate
  - Reason: Same as above

- `orchestrator._render` (`commands/wizard/orchestrator.py`)
  - Change: Verify it catches and handles `build()` / `regenerate()` exceptions correctly
  - Reason: Main entry point; must not crash ungracefully (FR-005)

**Tests:** Existing tests pass. No new tests required — build errors are tested in Phase 2 (T03).

---

## Phase 2: Regenerate Behavior

### T03 — Regenerate renders everything

**Files and changes:**

- `commands/regenerate.py:109-160`
  - Change: After scope and state validation (line 109):
    1. Call `build(scope, project_path, profile_label)` once
    2. Delete the per-CLI `generate_agent_files` block (`:125-142`)
    3. Loop over `installer.COMPONENT_TYPES` (agents, rules, config, skills, commands) with target-exists guard
    4. Count files placed per type; print ✓ only for non-empty counts
    5. Exit non-zero if target exists but source is None
  - Reason: Current code only renders agents; build() is called by install but not regenerate, leaving dist empty (D2, D3, FR-003, FR-004, FR-007)

- New: `tests/unit/commands/test_regenerate_fresh_package.py`
  - Change: DIST_* patched to empty tmp paths; verify regenerate places files; verify links resolve
  - Change: A no-op build variant (mocked) that raises SystemExit to verify regenerate exits non-zero on missing source
  - Change: Verify `agent-notes build` output does not contain "✓ skills" when dist is empty
  - Reason: Test the fresh-package defect (D2); SC-001, SC-003

- Update: `tests/unit/commands/test_regenerate_local_placement.py`
  - Change: Patch `agent_notes.commands.build.build` so tests don't hit real build
  - Reason: Tests now call `build()` for real; must mock it to keep tests deterministic (FR-003)

- Update: `tests/functional/commands/test_regenerate_command.py`
  - Change: Same as above
  - Reason: Regenerate now calls build; tests must patch it (FR-003)

- Update: `tests/functional/commands/test_config_review_flow.py`
  - Change: Same as above
  - Reason: Config calls regenerate; must patch build (FR-003)

**Tests:** All pass. New test fails on pre-fix code (regenerate places 0 files on empty dist).

---

### T04 — Regenerate keeps CLIs

**Files and changes:**

- `commands/regenerate.py:178`
  - Change: `build_install_state(...)` gets `selected_clis=set(scope_state.clis)`
  - Reason: Default build records every backend with dist content; regenerate must keep only the originally-installed CLIs (D4, FR-006)

- New: `tests/unit/commands/test_regenerate_preserves_clis.py`
  - Change: assert `build_install_state` called with `selected_clis`; assert manifest `clis` keys unchanged; assert claude config/rules/skills present; assert no opencode dir created
  - Reason: Verify regenerate does not widen the install (FR-006)

**Tests:** All pass. New test fails on pre-fix code (manifest shrinks/widens with dist content).

---

## Phase 3: Verification and Cleanup

### T05 — Truthful verify

**Files and changes:**

- `commands/_install_helpers.py:228` and `:244` (the item-present check in `_verify_install`)
  - Change: Replace `is_symlink()` with `exists()` (follows symlinks)
  - Reason: is_symlink() returns True for dangling links, making them appear present (D6, FR-008)

- `install.py:62-63` and `install.py:75-79` (rebuild error handling)
  - Change: Treat failed rebuild as error, not warning
  - Reason: Dangling links indicate failed install; must not mask with warning (FR-008)

- New: Unit test in `test_install_roundtrip` or new file
  - Change: Create a dangling symlink, verify `_verify_install` reports it missing; verify rebuild error is not downgraded
  - Reason: Verify the fix (FR-008, SC-002)

**Tests:** All pass. New test fails on pre-fix code (dangling links reported present).

---

### T06 — Verification and changelog

**Manual verification (not automated):**

1. Reproduce sandbox setup: clean venv, fresh install, pipx uninstall + reinstall, measure dangling links before/after `regenerate`.
   - Expected: 50 total, 32 dangling after reinstall, 0 after regenerate (SC-001)

2. Run `agent-notes doctor` on the sandbox install.
   - Expected: exits code 0 or appropriate error code, no ImportError (SC-002)

3. Run each new test against `git archive` of the pre-fix commit (e.g., 7fa3f76).
   - Expected: all new tests fail (SC-003)

4. Run full test suite.
   - Expected: green (`uv run pytest -q`, baseline 2241 passed, 15 deselected) (SC-004)

**Changelog:**

Update `CHANGELOG.md` `[Unreleased] / ### Fixed` with:
- Fixed dangling symlinks after reinstall by running full `build()` in `regenerate` (addresses #<issue>)
- Fixed `doctor` and `set_role` import errors introduced in #19
- Fixed `_verify_install` reporting dangling symlinks as present
- Fixed `regenerate` not placing rules, skills, config, or commands after fresh package install

**Spec:**

Record measured SCs in `spec.md` under a "## Verification Results" section.

**Tests:** All pass, including new tests. No code changes to tests after this point.

