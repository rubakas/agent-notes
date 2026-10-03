# 007 — Reinstall Replace Clean Isolate: Tasks

Ticket index for `plan.md`, which holds the code, tests and commands for each one. Every ticket is test-first and ends green.

## Phase A — Core Cleanup

- [ ] **T01 State fail-closed plus snapshot/ordering** — Distinguish absent from unreadable state. Snapshot old state at start, never clear before validation. Remove `--reconfigure` early clear. FR-A01, FR-A02, FR-A13.

- [ ] **T02 Ownership predicate module plus `_fix.py` adoption** — New `services/install_ownership.py` with `is_ours(path, manifest, old_venv_roots)` using lexical symlink target comparison (not `str.startswith`). `_fix.py` and `install_cleanup.py` use it. FR-A06.

- [ ] **T03 Placement manifest** — `install_state_builder.py` records only selected skills (not all available), commands, context file, `~/.agents/skills` mirror entries, and whole-tree SHA-256 hashes for copy mode. FR-A05.

- [ ] **T04 Cleanup set difference plus wiring** — New `services/install_cleanup.py` with `stale_placements(old_manifest, new_placements, shared_targets_claimed)` returning stale paths. Wire into `wizard/execute.py` and `commands/install.py` as place → clean → state. FR-A07, FR-A08.

- [ ] **T05 Fresh render inputs and lag fix** — Remove `_overlay_selection_pins` in fresh mode. Rendering gets explicit pins/efforts/memory/plugin-toggles from run. Memory and plugin changes take effect in the same install. FR-A03, FR-A04.

- [ ] **T06 Honest backups and plan count** — `fs.handle_existing` uses `is_ours` predicate. Unedited ours → no `.bak`; edited ours → `.bak`. Copy↔symlink flips replace owned entries. Foreign symlinks → `.bak`. Plan count accurate. FR-A09.

- [ ] **T07 Safe uninstall** — `commands/uninstall.py` reads state, uses `is_ours` predicate, removes only owned paths. Copy mode protects user files. `~/.agents/skills` entries included. FR-A10.

- [ ] **T08 Flags-path confirm, `--yes` and `--reconfigure` alias** — `commands/install.py` shows plan summary (replaced/removed items) on existing install with flags. `--yes` skips prompt; no TTY + no `--yes` → refuse. `--reconfigure` is no-op alias. Update tip text. FR-A11.

- [ ] **T09 Dist prune** — `build.py` prunes `dist/rules` and `dist/<cli>/agents` before rendering. Removed items stop being installed. FR-A12.

- [ ] **T10 Phase A verification** — Sandbox harness: run scenarios (i)–(vii) + upgrade-removed; compare A→B vs B-alone trees. User files survive (custom agent, rule, edited skill, foreign symlink). Unreadable state rejected. Failed place recoverable. All new tests fail pre-change; suite green. CHANGELOG updated. SC-001, SC-003–SC-007.

## Phase B — Per-Install Isolation

- [ ] **T11 `install_dirname` and `render_root`** — New `services/render_root.py` with `install_dirname(scope, project_path, label)` returning slug + 12-hex SHA-256; `render_root(scope, project_path, label)` returning `dist/` for default or `dist/installs/<dirname>/` for non-default. Owned roots extended. FR-B02, FR-B03.

- [ ] **T12 Render non-default installs into their tree** — `build.py` and `rendering.py` use `render_root()` for agents/global-config. Default install stays `dist/<cli>/…`; non-default goes to `dist/installs/<install_dirname>/<cli>/…`. Skills, rules, commands shared. FR-B01.

- [ ] **T13 Stamp, `render_stale` and "other installs" notice** — `.render.json` in each install tree: version + fingerprint of pins/efforts/memory/plugin-toggles/user-config-hash. Doctor reports `render_stale` with exact `regenerate` command. Post-install prints which other installs need regenerate. FR-B04.

- [ ] **T14 Shared-target warning** — `execute.py` warns when overwriting shared files that another install claims. Cleanup never removes shared targets while claimed. FR-B05.

- [ ] **T15 Uninstall removes render tree; regenerate/doctor RELINK use root** — `uninstall.py` removes `dist/installs/<dirname>` if stamp matches. `regenerate.py` and `doctor.py` RELINK use `render_root()`. FR-B06, FR-B07.

- [ ] **T16 Phase B verification** — Sandbox: reinstall default leaves other profiles byte-identical. Installing `work` with different pins leaves default agents byte-identical. All new tests fail pre-change; suite green. CHANGELOG updated. SC-002, SC-006, SC-007.

---

## Integration & Closure

After both phases:

- [ ] Full reinstall harness: sandbox install A, reinstall as B, compare trees.
- [ ] Uninstall and re-install scenario.
- [ ] Documentation: unsupported concurrent-install behavior per FR-A13.
