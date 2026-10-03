# 007 — Reinstall Replace Clean Isolate

**Feature Branch**: `develop` (direct)

**Created**: 2026-10-03

**Status**: Approved 2026-10-03

**Input**: "ensure that double install overrides old configs and do cleanup before installation of same profile" (user, 2026-10-03)

## Investigation

Method: install A then B in one HOME; install B alone in another; diff the trees. Verified in a non-editable sandbox build, fake HOME, 2026-10-03.

### Scenarios

Scenario → leftovers today:

- **(i) Same install twice.** Symlink mode is clean on disk, but the second install changes the content behind 19 links. Copy mode leaves 19 `.bak` files of our own earlier copies ("19 backed up"), because the first render saw no state and the memory text differs.
- **(ii) Skill subset (25 → 2).** 23 stale links in `~/.claude/skills` and 23 in `~/.agents/skills`. State still lists 25.
- **(iii) claude+codex → claude.** `~/.codex` is orphaned: 18 agent links, the `AGENTS.md` link, `agent-notes-context.md`, and a live SessionStart hook in `hooks.json`. State forgets codex.
- **(iv) symlink → copy.** Disk is right, but the plan said "Install 0 files" (`install_plan._plan_file:170`).
- **(v) copy → symlink.** 19 `.bak` of our own files. Rules, commands and skill dirs stay real copies while state says symlink.
- **(vi) Plugin on → off; memory change.** Both take effect one install late: the render and the session hook (`execute.py:253`) read the old persisted values (`rendering.py:399-401,511-515`), and the new ones are persisted after (`execute.py:280,286-293`).
- **(vii) Two profiles.** Files are isolated for Claude, but installing `work` with `worker=claude-haiku-4-5` re-rendered the shared `dist/`, and the default's `~/.claude/agents/coder.md` changed model. `install --profile work` also wrote `~/.codex`, `~/.config/opencode`, `~/.github` and `~/.agents/skills`.
- **Upgrade-removed skill.** Dangling links in `~/.claude/skills` and `~/.agents/skills`. A removed rule or agent keeps being installed, because `build.copy_global_files` (`build.py:20-38`) and `rendering.py:469-470` never prune.

## Root Causes and Risks

Verified by the lead against the code.

- **R1. Install is additive.** There is no diff against what the previous install placed (`execute.py:147-295`, `installer.install_all:66-86`).
- **R2. The manifest records `dist/`, not placements.** It records all skills from `DIST_SKILLS_DIR`, no commands, no context file, no mirror (`install_state_builder.py:136-158,193`), and it is replaced on reinstall. Skill dirs are hashed by `SKILL.md` only (`:144-147`).
- **R3. `--reconfigure` clears state before validating arguments** (`commands/install.py:86-88` before the `--copy` check at `:93`), so the old manifest is gone before cleanup could use it. The flags path's `build` (`:102`) uses persisted pins while `build_install_state` records none.
- **R4. `_overlay_selection_pins`** (`rendering.py:311-327`) preserves persisted pins for roles and CLIs the run didn't mention, which contradicts fresh semantics.
- **R5. `load_state`** (`state_store.py:28-37`) returns None on ANY parse error. The install flow then treats that as no state and overwrites every other install's entry.
- **R6. Deletion and backup hazards:**
  - `fs.handle_existing:86-103` backs up our own copies;
  - `fs.place_file:125-127` silently unlinks a foreign symlink;
  - `fs.remove_all_symlinks_in_dir:160-175` removes ANY symlink, and in copy mode every file and dir, so uninstall in copy mode deletes user files;
  - `install_executor.py:200,225-232` sweeps that way, including the cross-tool `~/.agents/skills`.
- **R7. Doctor's safe-delete has a bug.** `_fix.py:21,76` use a `startswith` prefix (`/x/dist-old` counts as inside `/x/dist`), and `safe_delete_paths` (`:50-61`) ignores `global_installs`.
- **R8. One shared `dist/`** for every install (`config.py:28`).
- **R9. Failures are swallowed.** `execute.py:255-256` (`except Exception: pass` on hooks) and `:282-283` (a failed state write is only a warning).

## Functional Requirements

### Phase A: Core Cleanup

- **FR-A01: fail closed on unreadable state.** State loading distinguishes absent from unreadable. If unreadable, install/uninstall/regenerate refuse to clean or overwrite, print the path and a recovery hint, and exit non-zero.
- **FR-A02: snapshot, never clear early.** Snapshot the old `ScopeState` read-only at the start of the run, and never clear state before the commit step. `--reconfigure` no longer calls `remove_install_state` up front, and all argument validation happens before any change.
- **FR-A03: fresh render inputs.** The render gets explicit inputs from this run (pins, efforts, memory, plugin toggles) and ignores the replaced install's persisted pins (no preserve-unmentioned overlay in fresh mode). The manifest records the pins actually used.
- **FR-A04: no one-install lag.** Memory and plugin choices of this run reach the render and the session hook in the same install. They are NOT persisted before confirm, so a decline changes nothing.
- **FR-A05: manifest records placements.** It lists selected skills only, commands, the context file and `~/.agents/skills` mirror entries. Copy mode hashes the whole tree of a directory.
- **FR-A06: one ownership predicate.** `is_ours(path, old_manifest)`:
  - a symlink whose lexical target (`os.readlink` + normpath, compared by path parts, never `str.startswith`) lies under an owned root: today `dist/`, plus legacy `…/agent_notes/dist/…` from any old venv;
  - OR a copy listed in the old manifest whose whole-tree sha matches.
  Anything doubtful is kept or moved to `.bak`, never deleted. `_fix.py` uses the same predicate, and its `safe_delete_paths` includes `global_installs`.
- **FR-A07: cleanup is a set difference.** `stale = owned(old manifest ∪ marker scan of the old target dirs, taken from the old state's overrides) − new placements − shared targets still claimed`. Claims are per (CLI, target dir): never remove under a target dir that another recorded install lists for that CLI. Confined to known roots.
- **FR-A08: order is place → remove stale → write state.** A failed state write or hook install is an error with a non-zero exit and a recovery command, not a warning.
- **FR-A09: honest backups.** Our own unedited copy is replaced with no `.bak`; an edited one is backed up. A copy↔symlink flip replaces owned entries. The plan's "N backed up" uses the same predicate. A foreign symlink at a target is renamed to `.bak`, never unlinked.
- **FR-A10: uninstall removes only what is ours.** No user files in copy mode, no foreign symlinks in swept dirs, `~/.agents/skills` included.
- **FR-A11: flags path on an existing install.** Confirm with a summary of replaced and removed items, `--yes` to skip; no TTY and no `--yes` → refuse with non-zero exit. `--reconfigure` is a no-op alias. Update the "Tip" text at `commands/install.py:73-83`.
- **FR-A12: prune dist.** `build` prunes `dist/rules` and `dist/<cli>/agents` before rendering, so removed items stop being installed.
- **FR-A13: concurrency is unsupported.** State and other installs' claims are read from one snapshot per run. Document it.

### Phase B: Per-Install Isolation

- **FR-B01: per-install render location.** The global default install keeps rendering into `dist/<cli>/…`, so it needs no migration. Every other install (global profiles, all local installs) renders its agents and global config files (`CLAUDE.md`, `AGENTS.md`, `copilot-instructions.md`) into `dist/installs/<install_dirname>/<cli>/…`. Skills, rules and commands stay shared in `dist/`.
- **FR-B02: `install_dirname(scope, project_path, label)`.** A slug for readability plus a 12-hex sha256 of `json.dumps([scope, resolved_project, label])`. Lowercase `[a-z0-9-]` only, stable, and a symlinked project path maps to its resolved path. The hash covers the whole identity tuple, so collisions are impossible in practice.
- **FR-B03: one `render_root(scope, project_path, label)` accessor**, used by build, rendering, `install_plan.dist_source_for`, `install_state_builder`, regenerate and doctor. Owned roots for FR-A06 are extended with `dist/installs/*`; a link into ANOTHER install's tree is not ours.
- **FR-B04: render stamp.** `.render.json` in each install tree holds the version and a fingerprint of all inputs (pins, efforts, memory, plugin toggles, user-config hash). Doctor reports `render_stale` with the exact `regenerate` command. After installing one install, print which other installs were rendered from different global inputs and need `regenerate`.
- **FR-B05: shared targets.** Last-writer-wins, plus a warning listing shared files overwritten that another install claims. Cleanup never removes them while claimed.
- **FR-B06: uninstall removes the install's render tree.** It must be under `dist/installs/` and its stamp identity must match.
- **FR-B07: regenerate and doctor's RELINK** use the install's `render_root`.

## Success Criteria

- **SC-001:** for every scenario (i)–(vii) plus the upgrade-removed case, A→B leaves the same tree as B alone, ignoring `.bak.<ts>` names and state timestamps. Measured in the sandbox harness.
- **SC-002:** reinstalling the default profile leaves `~/.claude-work` byte-identical. After 007b, installing `work` with different pins leaves the default's agent files byte-identical.
- **SC-003:** user-owned files survive reinstall and uninstall in both modes:
  - a user agent file, rule, skill, and a file edited inside a copied skill;
  - a foreign symlink in `~/.agents/skills`.
- **SC-004:** unreadable `state.json` → no cleanup, no overwrite, non-zero exit.
- **SC-005:** a failure while placing leaves the old links working, and re-running with the same choices converges.
- **SC-006:** every new test fails against the pre-change code (`git archive` of the base commit).
- **SC-007:** the full suite is green.

## Out of Scope

- Moving renders out of the package (XDG).
- `regenerate --all`.
- Plain `build` re-rendering every install.
- Per-install memory, plugins or user config.
- Review screen pre-fill.
- Locking for concurrent installs.
- The wizard's post-install summary rows.

## Owner's Environment

The owner's real `state.json` has a claude manifest shrunk to agents only and a phantom `opencode` entry (from a pre-006 `regenerate`, 2026-10-02). After 007a ships, the owner repairs it with an interactive `agent-notes install`, re-picking their pins. FR-A07's marker scan handles the incomplete manifest.

---

## Tickets

Detailed task breakdown in `tasks.md` and `plan.md`; each test-first, ends green; phases merge separately.

### Phase A: Core Cleanup

| Ticket | Title | Requirements | Scope |
|---|---|---|---|
| **T01** | State fail-closed plus snapshot/ordering | FR-A01, FR-A02, FR-A13 | `state_store.py` distinguishes absent from unreadable; snapshot old state read-only; never clear before commit; validate arguments first |
| **T02** | Ownership predicate module plus `_fix.py` adoption | FR-A06 | New `services/install_ownership.py` with `is_ours(path, manifest, old_venv_roots)` using lexical target comparison; `_fix.py` uses it |
| **T03** | Placement manifest | FR-A05 | `install_state_builder.py` records selected skills only, commands, context file, `~/.agents/skills` mirror; copy mode hashes whole trees |
| **T04** | Cleanup set difference plus wiring | FR-A07, FR-A08 | New `services/install_cleanup.py` with `stale_placements(old_manifest, new_placements, shared_targets_claimed)` returning stale paths; wire into `wizard/execute.py` and `commands/install.py` as place → clean → state |
| **T05** | Fresh render inputs and lag fix | FR-A03, FR-A04 | `rendering.py` gets explicit pins/efforts/memory/plugin-toggles from run, no overlay; memory and plugin changes live in hook and save before confirm |
| **T06** | Honest backups and plan count | FR-A09 | `fs.handle_existing` uses ownership predicate; unedited ours → no `.bak`; edited ours → `.bak`; copy↔symlink flips replace owned; foreign symlink → `.bak`; plan counts match |
| **T07** | Safe uninstall | FR-A10 | `commands/uninstall.py` uses ownership predicate; copy mode removes only ours; no user files; no foreign symlinks; `~/.agents/skills` included |
| **T08** | Flags-path confirm, `--yes` and `--reconfigure` alias | FR-A11 | `commands/install.py` shows plan summary (replaced/removed items), `--yes` skips; no TTY + no `--yes` → refuse; `--reconfigure` no-op alias; update tip text |
| **T09** | Dist prune | FR-A12 | `build.py` prunes `dist/rules` and `dist/<cli>/agents` before rendering; removed items stop being installed |
| **T10** | Phase A verification | SC-001, SC-003–SC-007 | Sandbox harness: run scenarios (i)–(vii) + upgrade-removed; compare A→B vs B-alone trees; user files survive; unreadable state rejected; failed place is recoverable; all new tests fail pre-change; suite green; CHANGELOG |

### Phase B: Per-Install Isolation

| Ticket | Title | Requirements | Scope |
|---|---|---|---|
| **T11** | `install_dirname` and `render_root` | FR-B02, FR-B03 | New `services/render_root.py` with `install_dirname(scope, project_path, label) -> str` (slug + 12-hex sha256); `render_root(scope, project_path, label) -> Path` returning `dist/` (default) or `dist/installs/<install_dirname>/`; lexical-target owned roots extended |
| **T12** | Render non-default installs into their tree | FR-B01 | `build.py` and `rendering.py` use `render_root()` for agents/global-config; default install stays `dist/<cli>/…`; non-default goes to `dist/installs/<install_dirname>/<cli>/…` |
| **T13** | Stamp, `render_stale` and "other installs" notice | FR-B04 | `.render.json` in each tree: version + fingerprint of pins/efforts/memory/plugin-toggles/user-config-hash; doctor reports `render_stale` with regenerate command; post-install prints which other installs need `regenerate` |
| **T14** | Shared-target warning | FR-B05 | `execute.py` warns when overwriting shared files (`~/.codex`, `~/.agents/skills`, project `CLAUDE.md` etc.) that another install claims; cleanup never removes them |
| **T15** | Uninstall removes render tree; regenerate/doctor RELINK use root | FR-B06, FR-B07 | `uninstall.py` removes `dist/installs/<install_dirname>` if stamp matches; `regenerate.py` and `doctor.py` RELINK use `render_root()` not `dist/` |
| **T16** | Phase B verification | SC-002, SC-006, SC-007 | Sandbox: reinstall default leaves other profiles byte-identical; installing `work` with different pins leaves default agents byte-identical; all new tests fail pre-change; suite green; CHANGELOG |

---

## Verification

To be measured after implementation.
