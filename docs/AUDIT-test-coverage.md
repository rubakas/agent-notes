# Test Coverage Audit

## Summary

- Public CLI commands (from `agent_notes/cli.py`): **13** — `install`, `build`, `uninstall`, `update`, `doctor`, `info`, `list`, `validate`, `set role`, `regenerate`, `memory`, `config`, plus `-v/--version`.
- Test files: **7** (4 functional, 1 integration, 2 plugin-artifact).
- Coverage:
  - **Fully covered (1)**: `config` (8 tests in `test_config_command.py`).
  - **Partially covered (2)**: `build` (2 unit tests + integration on the dist tree); `memory` (memory_backend internals well-covered, but no test invokes the `memory` command via the CLI dispatch).
  - **Untested (10)**: `install`, `uninstall`, `update`, `doctor`, `info`, `list`, `validate`, `set role`, `regenerate`, `--version`.

The integration suite covers build artifacts well (parametrized over every agent and skill). Functional coverage of the command layer is shallow — only `config` exercises the real command path with state. Top finding: the install/update/doctor lifecycle has no automated tests.

## Per-command matrix

### install
- Existing tests: none. Wizard and direct-mode install paths are untested.
- Gaps: dispatch (`--local`, `--copy`, `--reconfigure`), state writes, idempotency, abort-on-error.
- Recommended new tests:
  - `test_install_local_copy_mode_writes_files_into_project`
  - `test_install_local_symlink_mode_creates_symlinks`
  - `test_install_reconfigure_clears_state_for_scope`
  - `test_install_aborts_when_source_missing`
  - `test_interactive_install_dispatches_to_wizard_with_no_flags`

### build
- Existing tests: `tests/functional/test_build_commands.py:14:test_copy_skills_copies_all_skill_dirs`, `:42:test_copy_global_files_returns_list_of_paths`; integration coverage in `tests/integration/test_build_output.py`.
- Gaps: `build()` orchestration entry point, `copy_commands()`, error path on missing `agents.yaml`, line-counting summary.
- Recommended new tests:
  - `test_build_returns_when_agents_yaml_missing`
  - `test_copy_commands_copies_md_files_only`
  - `test_build_invokes_render_globals_and_copy_skills`

### uninstall
- Existing tests: none.
- Recommended new tests:
  - `test_uninstall_global_removes_claude_dir_files`
  - `test_uninstall_local_only_removes_project_files`
  - `test_uninstall_clears_state_for_scope`
  - `test_uninstall_is_idempotent_on_missing_target`

### update
- Existing tests: none.
- Recommended new tests:
  - `test_update_dry_run_shows_diff_no_writes`
  - `test_update_only_filter_limits_components`
  - `test_update_skip_pull_skips_git`
  - `test_update_yes_skips_prompt`

### doctor
- Existing tests: none.
- Recommended new tests:
  - `test_doctor_reports_missing_global_install`
  - `test_doctor_fix_repairs_broken_symlink`
  - `test_doctor_local_scope_only_checks_project`
  - `test_doctor_exits_non_zero_on_unfixable_issue`

### info
- Existing tests: none.
- Recommended new tests:
  - `test_info_prints_version_and_component_counts`
  - `test_info_handles_no_install_state`

### list
- Existing tests: none.
- Recommended new tests:
  - `test_list_agents_prints_agent_names`
  - `test_list_skills_prints_skill_names`
  - `test_list_models_includes_opus_sonnet_haiku`
  - `test_list_invalid_filter_errors`
  - `test_list_all_default_lists_everything`

### validate
- Existing tests: none.
- Recommended new tests:
  - `test_validate_passes_on_clean_data`
  - `test_validate_reports_invalid_yaml_in_agents_yaml`
  - `test_validate_reports_skill_missing_frontmatter`

### set role
- Existing tests: none. (Note: `config role-model` is tested and shares the same underlying logic; a regression in the `set role` dispatcher would not be caught.)
- Recommended new tests:
  - `test_set_role_updates_state_for_default_cli`
  - `test_set_role_with_cli_flag_targets_only_that_cli`
  - `test_set_role_rejects_unknown_model`
  - `test_set_role_rejects_unknown_role`

### regenerate
- Existing tests: none directly (mocked away inside config tests).
- Recommended new tests:
  - `test_regenerate_global_rewrites_dist_from_state`
  - `test_regenerate_with_cli_only_regenerates_one_target`
  - `test_regenerate_local_uses_local_state`

### memory
- Existing tests: 48 in `tests/functional/test_memory_backend.py` covering `_slug`, timestamps, `obsidian_write_note`, and `obsidian_regenerate_index`.
- Gaps: the `memory` command-layer wrapper itself (action dispatch: `init`/`list`/`add`/`size`/`show`/`reset`/`export`/`import`/`vault`/`index`).
- Recommended new tests:
  - `test_memory_add_with_minimal_args_writes_local_note`
  - `test_memory_add_obsidian_writes_to_correct_folder`
  - `test_memory_list_groups_by_agent`
  - `test_memory_reset_requires_confirmation`
  - `test_memory_export_then_import_roundtrips`
  - `test_memory_init_creates_index_md`

### config (NEW from Phase 4)
- Existing tests: `tests/functional/test_config_command.py:55–199` — `test_show_prints_current_state`, `test_role_model_scriptable_updates_state`, `test_role_model_updates_state_file`, `test_role_model_rejects_unknown_model`, `test_role_model_rejects_unknown_role`, `test_role_model_per_cli`, `test_apply_then_regenerate_called`, `test_apply_regenerate_skipped_on_no`, `test_quit_does_nothing`.
- Gaps: `role-agent` action is not covered; interactive `wizard` happy-path beyond quit is not covered.
- Recommended new tests:
  - `test_role_agent_assigns_agent_to_role`
  - `test_role_agent_rejects_unknown_agent`
  - `test_wizard_full_flow_assigns_then_applies`

### -v / --version
- Existing tests: none (only `test_pricing_yaml_loads` and entry-point check).
- Recommended new tests:
  - `test_version_flag_prints_version_string` (subprocess, asserts output matches `agent_notes/VERSION`).

## Cross-command tests (recommended)

- `test_round_trip_install_then_uninstall_leaves_no_files`
- `test_install_then_doctor_reports_clean`
- `test_install_then_config_role_model_then_regenerate_updates_dist`
- `test_install_then_update_dry_run_shows_no_diff`

## Style hygiene

- `tests/functional/test_config_command.py:117:test_role_model_per_cli` is **26 lines** — borderline; uses two nested `with patch.object` blocks. Consider extracting an `opencode_cli_state(state_file)` fixture to drop it under 20 lines.
- `tests/functional/test_memory_backend.py` — multiple test classes with deep filesystem fixtures, but each individual test is short (< 15 lines). No refactor needed; these are healthy.
- `tests/integration/test_build_output.py` — heavy reliance on session-scoped `built_dist` fixture which runs `python3 -m agent_notes build`. Slow once per session but amortized; acceptable.
- No tests use `MagicMock` chained more than two levels deep. No `unittest.mock` `side_effect` callable longer than 5 lines. No assertions over deep pickled state.
- No tests appear slower than ~1s individually except the one-time build subprocess in the session fixture.

## Backfill priority

1. (highest) **install / uninstall / update lifecycle** — these are the primary user-facing commands; today a regression here ships unnoticed.
2. **doctor `--fix`** — touches the filesystem destructively; needs guard-rails.
3. **memory command-layer dispatch** (action routing, not the backend internals which are well-tested).
4. **set role** — share-the-logic story with `config role-model` is fragile; a test pinned to the dispatcher prevents drift.
5. **list / info / validate** — quick to write, currently zero coverage.
6. **regenerate** — currently only exercised through mocked patches in config tests.
7. **`--version` flag** — one-line CLI smoke test.
8. **`config role-agent` and full wizard happy-path** — round out the already-good config suite.
