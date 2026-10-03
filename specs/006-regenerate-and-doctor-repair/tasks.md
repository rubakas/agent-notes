# 006 — Regenerate and Doctor Repair: Tasks

Ticket index for `plan.md`, which holds the code, tests and commands for each one. Every ticket is test-first and ends green.

## Phase 1 — Imports and basic repair

- [x] **T01 Import names** — Fix D1 (doctor crashes) and D1 (set_role crashes). Extend `test_import_health` to cover all files and verify imported names resolve. Add unmocked unit tests for diagnostics checks and a functional test for `doctor`. FR-001, FR-002, FR-009.

- [x] **T02 Build fails loudly** — `build.py:131-135` raises on missing agents config. Audit all callers. FR-005.

## Phase 2 — Regenerate behavior

- [x] **T03 Regenerate renders everything** — Delete per-CLI agent loop in `regenerate.py:125-142`. Call `build(scope, project_path, profile_label)` once after scope/state validation. Loop `COMPONENT_TYPES` (agents, rules, config, skills, commands) with target-exists guard. Count files placed. Exit non-zero if target exists but source is None. FR-003, FR-004, FR-007.

- [x] **T04 Regenerate keeps CLIs** — `regenerate.py:178` passes `selected_clis=set(scope_state.clis)` to `build_install_state`. Test: manifest keys unchanged; claude config/rules/skills present; no opencode dir created. FR-006.

## Phase 3 — Verification

- [x] **T05 Truthful verify** — `_install_helpers.py:228` and `:244` use `.exists()` not `.is_symlink()`. `install.py:62-63` treats failed rebuild as error. Test shows dangling link reported missing. FR-008.

- [x] **T06 Verification and changelog** — Sandbox repro: 32 dangling → 0 with regenerate alone. `doctor` exits code 0. All new tests fail against pre-fix. Suite green. Measured SCs recorded in `spec.md`; CHANGELOG updated. SC-001–SC-004.

