# 007 Implementation Plan

> **For agentic workers:** Use task-by-task execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement fresh install semantics with cleanup, per-install isolation, and robust state handling.

**Baseline:** Suite green. After each phase (A and B), the suite remains green and the phase merges independently.

---

## Phase A: Core Cleanup

### T01 — State fail-closed plus snapshot/ordering

**Files and changes:**

- `services/state_store.py:28-37` (`load_state`)
  - Change: Distinguish between file-not-found (returns None or empty state) and parse-error (raises with context)
  - Reason: Currently returns None on ANY error; callers cannot distinguish absent from corrupted (R5, FR-A01)

- `commands/install.py:73-92` (install orchestration)
  - Change: Snapshot old state at line 73; move argument validation (scope, paths, modes) before any state mutation; remove the `remove_install_state` call at `:86-88`
  - Reason: `--reconfigure` clears state before validation, losing the old manifest for cleanup (R3, FR-A02)

- `commands/uninstall.py`
  - Change: Read state at start, keep it read-only throughout
  - Reason: Supports snapshot pattern

- `commands/regenerate.py` and `commands/doctor.py`
  - Change: Adopt snapshot pattern; validate arguments before reading/writing state
  - Reason: Consistency; FR-A02, FR-A13

- Documentation: Add a note in relevant module docstrings about snapshot semantics and no concurrent installs (FR-A13)

**Tests:**

- New: `tests/unit/commands/test_install_state_fail_closed.py`
  - Corrupt `state.json` (invalid JSON); verify install/uninstall/regenerate/doctor each exit non-zero with the path and a recovery hint printed
  - Test: state snapshot not mutated on error

- New: `tests/unit/commands/test_install_snapshot_ordering.py`
  - Mock install with bad scope after snapshot; verify old state unmodified
  - `--reconfigure --bad-scope`: old state not cleared before validation error

- Existing tests: any that touched state clearing should still pass with the new pattern

---

### T02 — Ownership predicate module plus `_fix.py` adoption

**Files and changes:**

- New: `services/install_ownership.py`
  - Function: `is_ours(path: Path, old_manifest: ScopeState | None, old_venv_roots: list[Path]) -> bool`
    - Symlink case: read target with `os.readlink(path)`, normalize, split into parts, check if any part-sequence from old_venv_roots or `dist/` matches the target path-prefix (no `str.startswith`). Match wins.
    - Copy case: compute whole-tree SHA-256 of the file/dir and check against old manifest's record for that path (if present).
    - Default: return False (keep it, don't delete).
  - Reason: Correct ownership determination; used by cleanup, uninstall and doctor (R6, FR-A06)

- `services/diagnostics/_fix.py:50-61` (`safe_delete_paths`)
  - Change: Import and use `is_ours` for each path; pass `global_installs` from state
  - Reason: Current `startswith` is wrong; `_fix.py` must understand global_installs too (R7, FR-A06)

- `services/diagnostics/_fix.py:76` (the prefix-delete loop)
  - Change: Use `is_ours` instead of `startswith` check
  - Reason: Prevent false-positive matches

**Tests:**

- New: `tests/unit/services/test_install_ownership.py`
  - Symlink with various targets (under dist, under old venv, under home, foreign); verify correct is_ours result
  - Copy with matching/mismatching tree hash; verify correct result
  - Lexical symlink reading: relative links in a nested dir; verify correct normalization
  - Old venv roots: `/usr/local/venv/dist` and `~/.venv/dist` should both recognize their contents as owned; a link to `/somewhere/else` should not

---

### T03 — Placement manifest

**Files and changes:**

- `services/install_state_builder.py:136-158` (the manifest building in `build_install_state`)
  - Change: In the skills section, record only the selected skills passed in, not all of `DIST_SKILLS_DIR`
  - Reason: Manifest must match actual placement, not all available (R2, FR-A05)

- `services/install_state_builder.py:193` (manifest completion)
  - Change: Add `commands` field listing command files placed; add context file path; add `agents_skills_mirror` listing what goes to `~/.agents/skills`
  - Reason: Cleanup needs to know what was placed (FR-A05)

- `services/install_state_builder.py` (in copy-mode hash section)
  - Change: For each dir in agents/rules/skills, record the whole-tree SHA-256, not just filename
  - Reason: Copy ownership check needs it (FR-A05, FR-A06)

**Tests:**

- New: `tests/unit/services/test_install_manifest_placement.py`
  - Build with 5 selected skills, verify manifest lists exactly 5, not all available
  - Verify commands field is correct
  - Verify context file path is recorded
  - Verify copy-mode hashes are whole-tree SHA-256
  - Verify `agents_skills_mirror` lists all mirrored entries

---

### T04 — Cleanup set difference plus wiring

**Files and changes:**

- New: `services/install_cleanup.py`
  - Function: `stale_placements(old_manifest: ScopeState | None, new_placements: set[Path], shared_targets_claimed: dict[Path, set[str]]) -> set[Path]`
    - Input: old manifest (None if no previous state), new paths being placed, dict of shared target → CLIs that claim it
    - Algorithm: owned (from old manifest ∪ marker scan) minus new placements minus shared targets still claimed
    - Return: set of paths to remove
  - Reason: Implement the cleanup logic (R1, R7, FR-A07)

- `wizard/execute.py:147-295` (the placement loop)
  - Change (a): Compute the stale set from the snapshot old state and the planned new placements, as a pure function with no writes
  - Change (b): Place the new install via `installer.install_all`
  - Change (c): Remove the stale set from disk
  - Change (d): Write state, persisting the final manifest
  - Reason: Order is place → remove stale → write state; ensures removed items don't mask new ones; state reflects final disk state (FR-A08)

- `commands/install.py` (post-rebuild, pre-install section)
  - Change: Apply the same (a)–(d) order: compute stale, place, remove stale, write state
  - Reason: Consistent behavior across both paths (FR-A08)

- Wire the shared-targets-claimed dict from state (which installs claim which target dir)
  - For each CLI and target dir in state, build the dict mapping target → CLI set
  - Reason: Cleanup respects multi-install claims (FR-A07)

**Tests:**

- New: `tests/unit/services/test_install_cleanup_stale.py`
  - Old manifest lists /x/a, /x/b, /x/c; new placement lists /x/a, /x/d; verify stale = {/x/b, /x/c}
  - Owned symlink + foreign symlink in old; both still there in new placement; verify only owned is stale
  - Skill subset: old 5 skills, new 2; verify 3 are stale
  - Shared target (e.g., `~/.codex` claimed by 2 installs); removing one install does not delete the target
  - Orphaned `~/.codex` (old claimed, new does not); verify it is marked stale

- New: `tests/functional/commands/test_install_cleanup_placement_order.py`
  - Install A, then install A again with a skill subset; verify stale skills are removed after new ones are placed
  - A failure while placing leaves the old links working and no cleanup runs (SC-005)
  - A failed state write exits non-zero and prints the recovery command (FR-A08)

---

### T05 — Fresh render inputs and lag fix

**Files and changes:**

- `services/rendering.py:311-327` (`_overlay_selection_pins`)
  - Change: Remove or gate it behind fresh-mode flag; in fresh mode (default), do NOT overlay old persisted pins
  - Reason: Fresh semantics mean this run's choices are final, not merged with old state (R4, FR-A03)

- `services/rendering.py:399-401` (memory load)
  - Change: Accept explicit memory choice from the run (not persisted state)
  - Reason: New memory choice should take effect in this render, not one install later (FR-A04)

- `services/rendering.py:511-515` (plugin toggle load)
  - Change: Accept explicit toggles from the run
  - Reason: Plugin toggles should take effect immediately (FR-A04)

- `wizard/execute.py:253` (session hook install)
  - Change: Verify it reads the CURRENT render's plugin toggles, not persisted state
  - Reason: Hooks must match this install's config (FR-A04)

- `wizard/execute.py:280,286-293` (state persistence)
  - Change: Verify memory and plugin toggles are persisted AFTER confirm, not before
  - Reason: Decline must leave old state intact (FR-A04)

**Tests:**

- New: `tests/unit/commands/test_install_fresh_render_inputs.py`
  - Install with pins A, then same install with pins B; verify render uses B, not A+B overlay
  - Install with memory=built-in, then memory=obsidian; verify new memory in hooks and state
  - Plugin on→off: verify old hooks are not reinstalled; verify state reflects new value

- New: `tests/functional/commands/test_install_plugin_toggle_same_install.py`
  - Enable a plugin, install; disable it, reinstall same install; verify hook removed in the same install (not one later)

---

### T06 — Honest backups and plan count

**Files and changes:**

- `services/fs.py:86-103` (`handle_existing`)
  - Change: Use `is_ours` predicate to decide backup behavior
  - Reason: Only back up files we own; unedited ours are replaced (R6, FR-A09)

- `services/fs.py:86-103` (backup decision)
  - Change: Compute file hash for our own files; if it matches the previous version in manifest, replace with no `.bak` (unedited); if it differs, back up (edited)
  - Reason: Distinguish edited from unedited copies (FR-A09)

- `services/fs.py:125-127` (`place_file`, symlink unlink)
  - Change: If target exists and is a foreign symlink, rename to `.bak.<timestamp>` instead of unlinking silently
  - Reason: Preserve foreign symlinks; user can restore them (FR-A09)

- `services/install_plan.py` (the plan's file count)
  - Change: Count "backed up" as edited ours only (matches the `handle_existing` logic)
  - Reason: "19 backed up" must be accurate (FR-A09)

**Tests:**

- New: `tests/unit/services/test_fs_honest_backups.py`
  - Our unedited copy of a skill; verify it is replaced with no `.bak`
  - Our edited copy; verify `.bak` is created
  - Our symlink → copy flip; verify owned symlink is replaced, manifest updated
  - Foreign symlink in target dir; verify it becomes `.bak`, user can restore
  - Plan count: N files placed, M backed up (edited); verify M matches the backed-up files on disk

---

### T07 — Safe uninstall

**Files and changes:**

- `commands/uninstall.py`
  - Change: Read state; for the target install, snapshot its manifest
  - Change: For each path in the manifest, call `is_ours` with the snapshot
  - Change: Remove only the owned paths
  - Reason: Protect user files and foreign symlinks (R6, FR-A10)

- In copy mode:
  - Change: Never remove a dir if it might contain user files; only remove files/dirs explicitly in the manifest that we own
  - Reason: Avoid deleting user content (FR-A10)

- `~/.agents/skills` inclusion:
  - Change: Include entries from `agents_skills_mirror` in the manifest (FR-A05)
  - Change: Uninstall removes only the owned entries
  - Reason: Shared dir, but our specific links are removable (FR-A10)

**Tests:**

- New: `tests/unit/commands/test_uninstall_safe.py`
  - Uninstall with a user-edited file inside a copied skill; verify the dir is not removed, the file survives
  - Copy mode with foreign file in the target dir; verify uninstall removes only ours
  - Symlink mode with stale link; verify it is removed
  - `~/.agents/skills`: one entry ours, one foreign; verify only ours is removed

---

### T08 — Flags-path confirm, `--yes` and `--reconfigure` alias

**Files and changes:**

- `commands/install.py:73-83` (tip text)
  - Change: Update to reflect the new confirm step with `--yes` flag
  - Reason: Users need to know how to skip confirm (FR-A11)

- `commands/install.py` (the non-interactive install path for `install --local/--copy/--profile/…`)
  - Change: If any flags are set (not just `--reconfigure`), call the cleanup+place sequence, then show the plan summary (replaced items, removed items), then ask for confirm unless `--yes` is set
  - Reason: User sees what will change (FR-A11)

- `commands/install.py` (TTY check)
  - Change: If no TTY and no `--yes`, print error and exit 1
  - Reason: Non-interactive, unconfirmed destructive action is unsafe (FR-A11)

- `commands/install.py` (reconfigure handling)
  - Change: `--reconfigure` is now a no-op (it does not trigger the wizard; it just confirms the re-install flow)
  - Reason: `--reconfigure --copy` means "confirm and proceed with copy mode" (FR-A11)

**Tests:**

- New: `tests/functional/commands/test_install_flags_confirm.py`
  - `install --local` on an existing local install; shows plan summary with replaced items; user inputs y; install proceeds
  - Same, user inputs n; nothing is written, state unchanged
  - `install --local` with no TTY and no `--yes`; exit 1 with error message
  - `install --local --yes`; no prompt, install proceeds
  - `install --reconfigure --copy`: treated as a re-install confirmation (no new wizard)

---

### T09 — Dist prune

**Files and changes:**

- `build.py:20-38` (`copy_global_files`)
  - Change: Before copying/rendering, scan `dist/rules` and `dist/<cli>/agents` directories
  - Change: Remove entries that are no longer in the source (project or seed)
  - Reason: Removed rules/agents stop being installed (R12, FR-A12)

- `rendering.py:469-470` (the skills placement)
  - Change: Before rendering skills, check which are NOT selected and remove them from the target dist
  - Reason: Removed skills stop being installed (FR-A12)

**Tests:**

- New: `tests/unit/commands/test_build_prunes_dist.py`
  - Build with rules A, B, C; rebuild with rules A only; verify B and C are removed from dist before render
  - Build with skills 1–5; rebuild with skills 1, 3; verify skills 2, 4, 5 are removed from dist
  - Verify reinstall after pruning leaves no dangling links

---

### T10 — Phase A verification

**Manual and automated verification:**

1. Sandbox harness: run each scenario (i)–(vii) plus upgrade-removed case.
   - Compare A→B tree with B-alone tree (ignoring `.bak.<ts>` names and state timestamps).
   - Expected: trees match (SC-001).

2. User-file survival:
   - Create a user agent file in `~/.claude/agents/custom.md`; reinstall.
   - Create a user rule in `~/.claude/rules/custom.md`; reinstall.
   - Create a user skill (copy mode); edit a file inside it; reinstall.
   - Create a foreign symlink in `~/.agents/skills`; reinstall.
   - Expected: all survive (SC-003).

3. Unreadable state:
   - Corrupt `state.json` (invalid JSON); run `install`, `uninstall`, `regenerate`, `doctor`.
   - Expected: all exit non-zero with the path and recovery hint (SC-004).

4. Failed place recovery:
   - Mock `fs.place_file` to fail on the 5th file placement.
   - Run install; re-run with the same choices.
   - Expected: old links still work after failure, re-run converges (SC-005).

5. Test suite:
   - Run all new tests on pre-change code (git archive of base commit).
   - Expected: all new tests fail (SC-006).
   - Run full suite on new code.
   - Expected: green (SC-007).

6. **CHANGELOG update:**
   - Record in `CHANGELOG.md` `[Unreleased] / ### Changed`:
     ```
     - Install now removes stale files from the previous install (spec 007a)
     - Install on an existing install shows a summary and asks for confirmation (spec 007a)
     - State errors are fatal, not silent (spec 007a)
     ```

---

## Phase B: Per-Install Isolation

### T11 — `install_dirname` and `render_root`

**Files and changes:**

- New: `services/render_root.py`
  - Function: `install_dirname(scope: str, project_path: Path, label: str) -> str`
    - Compute `json.dumps([scope, str(project_path.resolve())], sort_keys=True)`, SHA-256, hex, first 12 chars
    - Slugify `label` to lowercase `[a-z0-9-]+` (hyphens, no underscores)
    - Return `f"{slug}-{hex12}"`
    - Reason: Readable, stable, collision-proof (FR-B02)

  - Function: `render_root(scope: str, project_path: Path, label: str) -> Path`
    - If scope is "global" and label is "default": return `DIST_DIR / scope` (no change, backward compatible)
    - Else: return `DIST_DIR / "installs" / install_dirname(...)`
    - Reason: Isolate non-default installs (FR-B03)

- Update modules to import and use `render_root` from `services.render_root` for use by build, rendering, install_state_builder, regenerate, doctor.

- Update `install_ownership.py:is_ours` to recognize owned roots:
  - `dist/` (default install)
  - `dist/installs/<any-install-dirname>/` (non-default installs)
  - Legacy `…/agent_notes/dist/…` (old venv paths, for backward compat)
  - Reason: Links into another install's tree are not ours (FR-B03)

**Tests:**

- New: `tests/unit/services/test_render_root.py`
  - Deterministic: same inputs always produce same output
  - Collision-free: different inputs produce different outputs (test 1000 combos)
  - Slug sanitization: `my_profile` and `my-profile` and `MY-PROFILE` all produce the same slug base
  - Symlink resolution: a symlinked project path resolves to the real path before hashing

---

### T12 — Render non-default installs into their tree

**Files and changes:**

- `build.py` (calls to rendering functions)
  - Change: Pass `render_root(scope, project_path, label)` to rendering functions instead of `DIST_DIR`
  - Reason: Non-default installs render to their own tree (FR-B01)

- `services/rendering.py` (all render functions that write to `dist/`)
  - Change: Accept `render_root: Path` instead of hardcoded `DIST_DIR`
  - Change: Agents and global-config files go to `render_root`; skills, rules, commands stay in shared `dist/`
  - Reason: Per-install isolation while sharing common components (FR-B01)

- `services/install_plan.py:dist_source_for`
  - Change: Use `render_root()` when looking up a component source
  - Reason: Query the right tree for each install (FR-B01)

- `services/install_state_builder.py`
  - Change: Use `render_root()` when recording manifest entries
  - Reason: Manifest points to the right tree (FR-B01)

**Tests:**

- New: `tests/unit/commands/test_build_per_install_render_location.py`
  - Default install renders to `dist/claude/agents/`
  - Global profile `work` renders to `dist/installs/<dirname>/claude/agents/`
  - Local install renders to `dist/installs/<dirname>/claude/agents/`
  - Skills, rules, commands always render to shared `dist/`
  - Verify paths in manifest match render_root (FR-B01)

---

### T13 — Stamp, `render_stale` and "other installs" notice

**Files and changes:**

- New: `.render.json` in each install's render tree
  - Structure: `{ "version": "1", "fingerprint": "<sha256>" }`
  - Fingerprint: SHA-256 of JSON dict with keys: selected pins per CLI/role, efforts, memory choice, plugin toggles, user-config file hash
  - Reason: Detect when the install is stale (inputs changed) (FR-B04)

- `services/rendering.py` (end of render)
  - Change: Compute fingerprint of current inputs; write `.render.json` to the render_root
  - Reason: Record input state for doctor (FR-B04)

- `services/diagnostics/_checks.py` (doctor checks)
  - Change: Add check `render_stale`: for each install, compare `.render.json` fingerprint to current global inputs
  - Change: If stale, report with the exact `regenerate --scope <scope> --project <path> --profile <label>` command
  - Reason: Tell user how to refresh (FR-B04)

- `wizard/execute.py` (post-install summary)
  - Change: After install, scan all other installs in state
  - Change: For each with a different fingerprint, print "⚠ Install `<label>` uses different settings; run: regenerate --scope … --project … --profile …"
  - Reason: Alert user to diverged installs (FR-B04)

**Tests:**

- New: `tests/unit/services/test_install_render_stamp.py`
  - Verify `.render.json` is written with fingerprint
  - Change pins; verify fingerprint changes
  - Change memory; verify fingerprint changes
  - Stable: same inputs → same fingerprint

- New: `tests/unit/services/test_doctor_render_stale.py`
  - Install A with pins X, install B with pins X
  - Change global pins to Y; verify doctor marks A as stale
  - Run regenerate for A; verify `.render.json` updated, stale mark gone

---

### T14 — Shared-target warning

**Files and changes:**

- `wizard/execute.py` (in the placement loop or before state write)
  - Change: For each shared target (`~/.codex`, `~/.agents/skills`, project-root `CLAUDE.md` etc.)
  - Change: If the new install overwrites a path claimed by another install, print warning with both install names
  - Reason: Alert user to the conflict (FR-B05)

- `services/install_cleanup.py:stale_placements`
  - Change: Never remove a shared target if another install claims it
  - Reason: Cleanup respects multi-install claims (FR-B05)

**Tests:**

- New: `tests/functional/commands/test_install_shared_target_warning.py`
  - Install A and B both using `~/.codex`; A overwrites; verify warning printed
  - Uninstall B; verify `~/.codex` survives (claimed by A)
  - Uninstall A; verify `~/.codex` removed

---

### T15 — Uninstall removes render tree; regenerate/doctor RELINK use root

**Files and changes:**

- `commands/uninstall.py`
  - Change: If the uninstalled install's render tree is under `dist/installs/`, remove it
  - Change: Verify stamp identity matches before removing (prevent accidental deletion)
  - Reason: Clean up per-install render artifacts (FR-B06)

- `commands/regenerate.py` (RELINK)
  - Change: Use `render_root()` instead of hardcoded `dist/`
  - Reason: Regenerate the right tree (FR-B07)

- `services/diagnostics/_checks.py` (RELINK in doctor)
  - Change: Use `render_root()` instead of hardcoded `dist/`
  - Reason: Doctor fixes the right tree (FR-B07)

**Tests:**

- New: `tests/functional/commands/test_uninstall_per_install_tree.py`
  - Install default and profile `work`; uninstall `work`; verify `dist/installs/<work-dir>` removed, `dist/claude/…` stays
  - Uninstall default; verify `dist/…` still exists (used by other installs), `dist/installs/…` stays

- New: `tests/unit/commands/test_regenerate_uses_render_root.py`
  - Regenerate default install; verify changes in `dist/claude/agents/`
  - Regenerate profile `work`; verify changes in `dist/installs/<dirname>/claude/agents/`

---

### T16 — Phase B verification

**Manual and automated verification:**

1. Byte-identical isolation:
   - Install default (A), install profile `work` (B); measure agent files in `~/.claude/`.
   - Reinstall default with same pins; measure again.
   - Expected: byte-identical (SC-002).
   - Reinstall default with different pins; measure default's agents.
   - Expected: work's agents unchanged (SC-002).

2. Test suite:
   - Run all new tests on pre-change code.
   - Expected: all new tests fail (SC-006).
   - Run full suite on new code.
   - Expected: green (SC-007).

3. **CHANGELOG update:**
   - Record in `CHANGELOG.md` `[Unreleased] / ### Changed`:
     ```
     - Profiles and local installs now render agents to isolated directories (spec 007b)
     - Doctor detects stale render input and suggests regenerate (spec 007b)
     ```

---

## Integration Tests

After both phases ship:

- Full reinstall harness in CI: sandbox install A, reinstall as B, compare trees (SC-001).
- Uninstall and re-install in sandbox.
- Concurrent-install scenario (document unsupported behavior per FR-A13).

---

## Success Checkpoints

- **After T10 (Phase A):** scenarios (i)–(vii) pass in sandbox; user files survive; unreadable state is rejected; test suite green.
- **After T16 (Phase B):** isolation confirmed; installs render to separate trees; doctor detects stale; test suite green.
