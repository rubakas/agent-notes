# Test categorization map (Phase 11.1)

## Summary
- Total test files: 15 (excluding `__init__.py` and `conftest.py`)
- Total tests collected: 482
- Currently skipped: 126
- Files needing split (mixed concerns): 2
- Files recommended for deletion: 0

## Mapping table

| Current path | → | Proposed path | Reason | Skips | Notes |
|---|---|---|---|---|---|
| tests/functional/test_build_command.py | → | tests/functional/build/test_build_command.py | build command orchestration | 0 | heavy mocking of build internals; tests behavior not output |
| tests/functional/test_build_commands.py | → | tests/unit/services/test_build_functions.py | unit tests of `copy_skills` and `copy_global_files` in isolation | 0 | pure unit — no CLI invocation, no state, no I/O beyond tmp_path; misclassified as functional |
| tests/functional/test_config_command.py | → | tests/functional/commands/test_config_command.py | config command (show, role_model, interactive) | 0 | patches `_safe_input`; real state I/O via tmp_path |
| tests/functional/test_credentials.py | → | tests/unit/services/test_credentials.py | credentials service unit tests | 0 | pure service layer; no command invoked; fast, no external deps |
| tests/functional/test_doctor.py | → | tests/functional/commands/test_doctor_command.py | doctor command with stubbed checks | 0 | all check functions mocked; tests command wiring |
| tests/functional/test_info.py | → | tests/functional/commands/test_info_command.py | info command output | 0 | single command entry point, real state via tmp_path |
| tests/functional/test_install_lifecycle.py | → | tests/functional/commands/test_install_command.py | install command lifecycle | 0 | build patched; installer patched; tests state transitions |
| tests/functional/test_list.py | → | tests/functional/commands/test_list_command.py | list command (clis/skills/agents/unknown) | 0 | clean; 4 independent tests |
| tests/functional/test_memory_backend.py | → | tests/unit/services/test_memory_backend.py | memory_backend service unit tests | 0 | tests private functions (`_slug`, `_now`, `_today`, `_current_session_id`) and write/index directly; no CLI; 449 lines — split candidate (see below) |
| tests/functional/test_memory_command.py | → | tests/functional/memory/test_memory_command.py | memory command dispatch (list/add/index/show/vault) | 0 | real obsidian vault in tmp_path; integration-ish but single command |
| tests/functional/test_regenerate.py | → | tests/functional/commands/test_regenerate_command.py | regenerate command | 0 | clean; 3 tests |
| tests/functional/test_registries.py | → | tests/unit/registries/test_registries.py | registry load tests (model/role/skill/agent) | 0 | pure unit — only reads YAML from `data/`; no I/O; no state; fast |
| tests/functional/test_release_script.py | → | tests/functional/scripts/test_release_script.py | release script smoke tests | 1 | 1 skip (dirty repo); uses subprocess; second test always runs |
| tests/functional/test_uninstall.py | → | tests/functional/commands/test_uninstall_command.py | uninstall command lifecycle | 0 | clean; tests symlink removal, state cleanup, idempotency |
| tests/functional/test_update.py | → | tests/functional/commands/test_update_command.py | update command (build, install, dry-run) | 0 | clean; 3 tests |
| tests/functional/test_validate.py | → | tests/functional/commands/test_validate_command.py | validate command (mixed) | 1 | 1 skip (requires built dist); `TestValidatePassesOnCleanData` uses `built_dist` fixture — split this test to integration |
| tests/integration/test_build_output.py | → | tests/integration/build_output/test_build_output.py | build output filesystem assertions | 16 | 16 skips (built_dist fails); 4 tests (`test_cost_report_*`, `test_pricing_*`, `test_normalize_*`) do NOT use `built_dist` — split candidate |
| tests/integration/test_plugin_builders.py | → | tests/integration/plugin_builders/test_plugin_builders.py | plugin builder scripts (claude/opencode) | 0 | spawns subprocess; writes to real `.claude-plugin/` and `.opencode-plugin/` in repo root — mutates repo tree, not tmp_path |
| tests/plugins/test_agents.py | → | tests/plugins/claude/test_agents.py | parametrized built agent file validation | 108 | 108 skips (built_dist fails); parametrize runs at collection time against live dist — if dist absent, all 108 tests skip |
| tests/plugins/test_skills.py | → | tests/plugins/test_skills.py | parametrized source skill SKILL.md validation | 0 | reads `data/skills/` directly, no build required; clean; stays at plugins root |

## Skips inventory

**126 total skips, 3 distinct causes:**

### 1. "Build failed" — `built_dist` session fixture (123 skips)
**Files**: `test_build_output.py` (16), `test_agents.py` (108 — 6 tests × 18 agents), `test_validate.py::TestValidatePassesOnCleanData` (1 — uses `built_dist` directly).

**Root cause**: `conftest.py:built_dist` runs `python3 -m agent_notes build`. In this environment (dirty tree, missing dependencies, or the build command itself failing), the fixture calls `pytest.skip()` and all dependents cascade-skip.

**Recommendation**: **(b) convert to `@pytest.mark.requires_build`** — deselect in fast-feedback runs (`pytest -m "not requires_build"`), not skip. The `built_dist` fixture should raise, not skip, so failures surface as errors rather than silently disappearing into the skip count. The 123 "Build failed" skips mask whether the build is broken or just not run.

### 2. Dirty working directory — `test_release_script_dry_run_exits_zero_on_clean_repo` (1 skip)
**File**: `test_release_script.py:26-27` — two stacked `@pytest.mark.skipif`: one for missing `build`/`twine`, one for dirty repo.

**Recommendation**: **(b) convert to `@pytest.mark.requires_clean_repo`** — makes it deselectable. The dirty-repo check is evaluated at import time (`_repo_dirty`), which means it cannot be overridden without editing the file. Move the check inside a fixture.

### 3. Implicit skip via empty parametrize — `test_agents.py` also
When `_CLAUDE_AGENTS_DIR` does not exist, `_agent_files()` returns `[]`, so `AGENT_FILES` is empty. Pytest silently collects 0 parametrized cases rather than failing. This is a **silent failure mode**, not a proper skip — no "skipped N" message, no reason string, just 0 tests run. This should be guarded with a fixture that errors if dist is absent.

## Files recommended for deletion

None. All files test real behavior that should be preserved.

## Files needing split (mixed concerns)

**`tests/functional/test_memory_backend.py` → split into two**
- Move `TestSlug`, `TestTimestampHelpers`, `TestUtcTimestamps`, `TestCurrentSessionId`, `TestSessionNoteFilename`, `TestSessionFrontmatterMigration`, `TestSessionFrontmatter` → `tests/unit/services/test_memory_backend_unit.py` (pure function tests, no I/O)
- Move `TestObsidianWriteNote`, `TestObsidianRegenerateIndex` → `tests/unit/services/test_memory_backend_io.py` or keep in functional/memory/ (these write to tmp_path)

**`tests/integration/test_build_output.py` → split into two**
- `test_cost_report_entry_point_registered`, `test_cost_report_module_imports`, `test_pricing_yaml_loads`, `test_normalize_model_dashed_to_dotted` — do NOT use `built_dist`; move to `tests/unit/scripts/test_pricing.py` or `tests/unit/scripts/test_cost_report.py`
- Everything else stays in `tests/integration/build_output/` and requires the build

## Cross-cutting fixtures

**`conftest.py::built_dist`** (session-scoped): Used by `test_build_output.py`, `test_validate.py::TestValidatePassesOnCleanData`, and `test_agents.py`. After the split:
- Phase 11 should move `built_dist` to a `tests/integration/conftest.py` and a separate `tests/plugins/conftest.py` (or a shared `tests/conftest.py` limited to integration/plugins scopes).
- The fixture should call `pytest.fail()` not `pytest.skip()` when the build command errors, so failures are visible as errors.
- `test_agents.py` uses `require_built_dist` as a module-level `autouse` fixture but also relies on collection-time `_agent_files()` — this creates a race: files are globbed before the fixture runs. Phase 11 must fix collection order (move glob into fixture, use `pytest_generate_tests`).

## Open questions

1. **`test_plugin_builders.py` writes to the real repo root** (`.claude-plugin/plugin.json`, `.opencode-plugin/index.js`) rather than `tmp_path`. Is this intentional (tests the real artifact locations) or a gap? If intentional, it cannot run in parallel. If not, it should write to a temp directory and belongs in `tests/functional/scripts/` not `tests/integration/`.

2. **`test_registries.py`**: reads from `agent_notes/data/` (source YAML files). This is genuinely unit-level but touching source data. Should these live under `tests/unit/registries/` or `tests/functional/` given they validate that source data is well-formed?

3. **`test_agents.py` parametrize-at-collection-time pattern**: The `AGENT_FILES = _agent_files()` call at module level means test IDs are empty when dist is absent. Phase 11 needs to decide: require dist to be pre-built before collection runs, or restructure as a non-parametrized loop inside a single test function.
