# Memory Provider Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`. Rescoped #39 (see issue). Branch `refactor/plugin-system`.

**Goal:** Model memory as a provider (`local` default / `obsidian`) that is always on, with an obsidian `strategy` (`single-brain` / `per-project`), and no `none`/disable. Configured via `config memory` + the wizard — NOT via `plugins`.

**Architecture:** Add a `strategy` field to `MemoryConfig`; migrate legacy `backend: none` → `local` on load; branch the obsidian backend on strategy; rework the memory step of config/wizard; sweep out every `if backend == "none"` path. Memory is not in the boolean plugin registry.

## Global Constraints

- **Default (`local`) install stays byte-identical.** Verify with `scripts/dev/verify_dist_equiv.sh <pre-#39-commit>` (the commit before Task M1). NEVER `git diff` the gitignored `agent_notes/dist/`.
- **No data loss.** Switching strategy or migrating `none`→`local` must never delete a user's existing notes.
- No new deps; no AI attribution; commit `#39 type(scope): …` title-only; TDD (failing test first).
- Suite is `1850 passed, 15 deselected` at plan start — keep green.

---

### Task M1: MemoryConfig schema — add `strategy`, drop `none`, migrate none→local

**Files:** `agent_notes/domain/state.py` (MemoryConfig), `agent_notes/services/state_store.py` (load/save), `agent_notes/commands/doctor.py` (`_VALID_MEMORY_BACKENDS`). Test: `tests/unit/…/test_memory_config_migration.py`.

**Interfaces produced:** `MemoryConfig(backend: str = "local", path: str = "", strategy: str = "single-brain")`; state load maps `backend == "none"` → `"local"` (and leaves strategy at default); save persists `strategy`.

- [ ] **Step 1 (failing test):** legacy state JSON with `{"memory": {"backend": "none", "path": ""}}` loads as `backend == "local"`; a fresh MemoryConfig has `strategy == "single-brain"`; an obsidian state with `strategy: "per-project"` round-trips through save→load.
- [ ] **Step 2:** run → fails (no `strategy` field / no migration).
- [ ] **Step 3:** add `strategy` to `MemoryConfig` (default `"single-brain"`), update the `# "obsidian" | "local" | "none"` docstring to `"obsidian" | "local"` + note strategy is obsidian-only. In `state_store` load (`MemoryConfig(...)` construction ~line 237): read `strategy` (default `"single-brain"`), and `backend = "local" if raw == "none" else raw`. In save (`{"memory": {...}}` ~line 189): include `strategy`. In doctor, `_VALID_MEMORY_BACKENDS = {"obsidian", "local"}`.
- [ ] **Step 4:** run → green.
- [ ] **Step 5:** full suite; then `scripts/dev/verify_dist_equiv.sh <pre-M1-commit>` → BYTE-IDENTICAL (schema change doesn't alter built output for a default/local install).
- [ ] **Step 6:** commit `#39 feat(memory): add obsidian strategy field and migrate none-backend to local`.

**Dist: byte-identical.**

---

### Task M2: obsidian backend strategy-aware placement (NO on-the-fly conversion)

**User directive (locked):** switching provider/strategy MUST NOT touch, move, or convert previously-created notes. Old notes stay exactly where they are; only NEW notes/sessions/docs are written to the new destination in the new strategy's format. There is no automatic migration on switch.

**Files:** `agent_notes/memory/obsidian_backend.py`. Tests: placement of a NEW note under each strategy; recall still finds pre-existing notes written under the other strategy.

- Reads current `state.memory.strategy` when deciding where to WRITE a new note/session:
  - `single-brain`: flat shared root (current behavior — unchanged).
  - `per-project`: under a project subfolder, keyed by the current project name (`_current_project_name()` = cwd name, matching the existing convention; note the collision caveat for same-named dirs).
- **No conversion, no `migrate` changes.** Leave `memory/commands/migrate.py` as the existing explicit one-way per-project→flat tool; it is NOT invoked by switching and is out of scope here.
- **Never hide old notes.** Read/list/recall operations must still surface notes that were written under a different prior strategy (e.g. search the flat root AND project subfolders), so a switch never makes past notes disappear from recall — it just changes where new ones land.
- Default `single-brain` reproduces today's write paths exactly.

**Dist: byte-identical.** **Tests:** new-note placement per strategy; a note pre-existing in the flat root is still found after switching to `per-project` (nothing moved, nothing hidden).

---

### Task M3: wizard + `config memory` UX — provider then strategy, no `none`

**Files:** `agent_notes/commands/config.py` (`_wizard_memory` ~line 481), `agent_notes/commands/wizard/` (`_select_memory`), `agent_notes/commands/wizard/execute.py:287`.

- Replace the `local / obsidian / none` menu with: (1) provider `local` / `obsidian`; (2) if obsidian, strategy `single-brain` / `per-project` (+ vault path). No `none`.
- `execute.py:287` `if memory_backend != "none"` → drop the none case; always configure a provider (default local).
- Persist `strategy` through the wizard→execute→state path.

**Dist: byte-identical** for equivalent (default local) selections.

---

### Task M4: remove every `none` path; define `local` behavior for memory commands

**Files:** `agent_notes/memory/commands/{reset,transfer,vault,notes}.py`, `agent_notes/memory/instructions.py`, `agent_notes/commands/doctor.py` (done in M1 for the valid set).

- Each `if backend == "none":` branch is removed. For each memory command, define the `local` behavior explicitly: operate on the CLI's native md-file memory where it makes sense; for genuinely obsidian-only operations (e.g. vault-specific), print a clear "this applies to the obsidian provider" message instead of the old "memory disabled".
- `instructions.py`: the `backend == "none"` case (no memory instructions rendered) is replaced by the `local` instructions — memory guidance is always present now.

**Dist: EXPECTED DIFF** — `instructions.py` feeds `{{MEMORY_INSTRUCTIONS}}` into built files; removing the none-case changes what a `none`(→now `local`) user gets. Review the diff; it should equal "local memory instructions now render where none rendered nothing." Verify against a pre-M4 build with an explicit local fixture, not a blanket byte-identical claim.

---

## Self-Review

- Coverage: provider model (M1 schema+migration), obsidian strategies (M2), UX (M3), none-sweep + local semantics (M4). Ticket #39's three open sub-decisions map to: strategy-always-present (M1), local command behavior (M4), migrate bidirectional guardrails (M2).
- Risk: M4 is the only expected-diff task; M1–M3 are byte-identical for default/local. M2's migrate must be data-loss-safe — the highest-risk step; test it hardest.
- Sequence: M1 → M2 → M3 → M4 (schema before backend before UX before the none-sweep).
