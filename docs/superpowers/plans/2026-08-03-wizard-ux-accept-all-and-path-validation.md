# Wizard UX — Accept-All Defaults + Obsidian Path Validation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Two targeted UX improvements to the install wizard: (1) an "accept recommended models/effort for all roles" gate that short-circuits the per-role gauntlet in step 2; (2) validation + a re-enter/use-anyway loop on the Obsidian vault path in step 7.

**Architecture:** Both changes live in `agent_notes/commands/wizard/__init__.py`. Feature 1 extracts the existing per-role default-model computation into a helper so the accept-all path and the interactive path share it (DRY), then adds a single gate before the loop. Feature 2 wraps the existing `_path_input` call in a validate/confirm loop.

**Tech Stack:** Python 3.14, pytest, `agent_notes/commands/wizard/`, `agent_notes/services/ui.py` (`_radio_select`, `_path_input`, `_can_interactive`).

## Global Constraints

- **NOT byte-identical** — these change behavior deliberately. The gate is a NEW interactive prompt; validation is NEW. Do NOT run `verify_dist_equiv.sh` as a pass/fail gate. Instead: for *equivalent final selections* dist should still match, but that is not the acceptance bar here.
- **Full suite green:** `uv run pytest tests/` MUST pass. Existing wizard tests that drive the flow (esp. `tests/functional/commands/test_wizard_happy_path.py`) will need their mocked-input sequence updated for the new gate prompt — update them, don't delete assertions.
- **`TOTAL_STEPS` unchanged (still 9):** both features are sub-prompts *within* existing steps (2 and 7), not new numbered steps. Do NOT touch `_compute_total_steps` or the orchestrator.
- **Non-interactive behavior preserved:** when `_can_interactive()` is False, the accept-all path is taken silently (same end result as today's fallback-to-defaults), and path validation does NOT loop (takes the path as-is, as today). No CI/scripted install may start blocking on a prompt.
- **Defaults unchanged:** the model/effort a role gets under "accept all = yes" MUST equal what the current per-role default pre-selection produces. This is the DRY requirement — extract, don't re-derive differently.

---

### Task 1: "Accept recommended for all roles" gate in step 2

**Files:**
- Modify: `agent_notes/commands/wizard/__init__.py` (`_select_models_per_role`, ~lines 102-214)
- Test: `tests/unit/commands/test_wizard_accept_all_models.py` (create); update `tests/functional/commands/test_wizard_happy_path.py`

**Interfaces:**
- `_select_models_per_role(clis, step, total, version) -> tuple[dict, dict]` — signature UNCHANGED; only its internal flow changes.
- New private helper `_default_model_for_role(role, compatible) -> model` extracted from the existing default-selection logic (the `default_model = next(...)` chain at ~lines 149-158).

- [ ] **Step 1: Read the current code**

Read `_select_models_per_role` in full (`__init__.py:102-214`). Identify: the per-backend loop, the `compatible` computation, the `default_model = next(... typical_class ... not deprecated ... not never_default ...)` chain (~149-158), the effort default via `_effort_default_choice` (~90-99 / ~197), and the claude-orchestrator skip (~146).

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/commands/test_wizard_accept_all_models.py`. These tests monkeypatch `_can_interactive` and the radio-select functions to assert prompt behavior:

```python
import agent_notes.commands.wizard as wiz


def test_accept_all_yes_skips_per_role_prompts(monkeypatch):
    # Gate returns "yes"; per-role model radios must NOT be called.
    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    calls = {"gate": 0, "per_role": 0}

    def fake_gate(*a, **k):
        calls["gate"] += 1
        return "yes"

    def fake_radio(*a, **k):
        calls["per_role"] += 1
        raise AssertionError("per-role radio should not run when accept-all=yes")

    # _select_gate_accept_all is the new helper; per-role uses _radio_select
    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: True)
    monkeypatch.setattr(wiz, "_radio_select", fake_radio)

    role_models, role_efforts = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

    # claude skips orchestrator; the other roles get their computed defaults, no prompts
    assert "claude" in role_models
    assert "orchestrator" not in role_models["claude"]
    assert len(role_models["claude"]) >= 1  # defaults populated without prompting


def test_accept_all_no_falls_through_to_per_role(monkeypatch):
    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: False)
    picked = {}

    def fake_radio(title, options, default=0, **k):
        # user accepts each highlighted default
        return options[default][1]

    monkeypatch.setattr(wiz, "_radio_select", fake_radio)
    role_models, _ = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")
    assert "claude" in role_models and len(role_models["claude"]) >= 1


def test_accept_all_yes_matches_per_role_defaults(monkeypatch):
    # The models chosen by accept-all=yes must EQUAL the models chosen by
    # accept-all=no + accepting every highlighted default. (DRY / no drift.)
    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    monkeypatch.setattr(wiz, "_radio_select", lambda title, options, default=0, **k: options[default][1])

    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: True)
    yes_models, yes_efforts = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: False)
    no_models, no_efforts = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

    assert yes_models == no_models
    assert yes_efforts == no_efforts
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/commands/test_wizard_accept_all_models.py -v`
Expected: FAIL — `_select_accept_all_models` does not exist.

- [ ] **Step 4: Extract the default-model helper**

Extract the `default_model = next(...)` chain (~lines 149-158) into a module-level helper so both paths use it verbatim:

```python
def _default_model_for_role(role, compatible):
    """The pre-selected default model for a role given the backend's compatible models."""
    return next(
        (m for m in reversed(compatible) if m.model_class == role.typical_class and not m.deprecated and not m.never_default),
        next(
            (m for m in reversed(compatible) if m.model_class == role.typical_class and not m.never_default),
            next(
                (m for m in reversed(compatible) if not m.never_default),
                compatible[0],
            ),
        ),
    )
```

In the interactive loop, replace the inline chain with `default_model = _default_model_for_role(role, compatible)` and keep `default_idx = compatible.index(default_model)`.

- [ ] **Step 5: Add the gate + accept-all path**

Add the gate helper (interactive only):

```python
def _select_accept_all_models(step, total, version=''):
    """Ask whether to accept recommended models/effort for every role. Default Yes."""
    options = [
        ("Yes  — use the recommended model and effort for every role", "yes"),
        ("No   — choose the model (and effort) per role", "no"),
    ]
    if _can_interactive():
        choice = _radio_select(
            "Use recommended models for all agent roles?\n"
            "  (you can change any of them later with: agent-notes config role-model)",
            options, default=0, step=step, total=total, version=version,
        )
        return choice == "yes"
    return True  # non-interactive: accept recommended silently (today's behavior)
```

At the top of `_select_models_per_role`, after computing `roles_sorted` and before the backend loop, call the gate ONCE:

```python
    accept_all = _select_accept_all_models(step=step, total=total, version=version)
```

Inside the per-role loop, branch: if `accept_all`, pick `default_model` (via the helper) and the default effort **without prompting** and print a compact confirmation; else run the existing `_radio_select` prompts. Factor the effort default the same way (reuse `_effort_default_choice`). The accept-all branch must still honor the claude-orchestrator skip and the "no compatible models" warning.

- [ ] **Step 6: Run the new tests + update the happy-path test**

Run: `uv run pytest tests/unit/commands/test_wizard_accept_all_models.py -v` → PASS.

Update `tests/functional/commands/test_wizard_happy_path.py`: its mocked input sequence now hits the gate prompt at step 2. Simplest fix that preserves coverage — make the test answer the gate with **"no"** so the existing per-role assertions still exercise the interactive path; add a second happy-path variant (or parametrize) that answers **"yes"** and asserts the per-role radios are not invoked. Run it to green.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest tests/` → PASS (existing `test_wizard_orchestrator_skip.py` / `test_wizard_role_ordering.py` must still pass — the accept-all=no path is the old behavior; accept-all=yes must produce the same role_models).

- [ ] **Step 8: Commit**

```bash
git add agent_notes/commands/wizard/__init__.py tests/unit/commands/test_wizard_accept_all_models.py tests/functional/commands/test_wizard_happy_path.py
git commit -m "feat(wizard): add 'use recommended models for all roles' shortcut to step 2"
```

---

### Task 2: Obsidian vault path validation + re-enter loop

**Files:**
- Modify: `agent_notes/commands/wizard/__init__.py` (`_select_memory`, the obsidian path branch ~lines 363-374)
- Test: `tests/unit/commands/test_wizard_memory_path_validation.py` (create)

**Interfaces:**
- `_select_memory(step, total, version) -> tuple[str, str, str]` — signature UNCHANGED. New private helper `_validate_vault_path(path) -> tuple[bool, str]` returning `(is_ok, reason)` where reason is a short human message when not ok.

- [ ] **Step 1: Read the current code**

Read the obsidian branch of `_select_memory` (`__init__.py:~363-374`): the detected-vault default, the `_path_input(...)` call, and the `path = str(Path(vault) / subfolder)` join. Confirm there is NO existence/`.obsidian` check today.

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/commands/test_wizard_memory_path_validation.py`:

```python
import agent_notes.commands.wizard as wiz


def test_validate_vault_path_accepts_real_vault(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    ok, reason = wiz._validate_vault_path(str(tmp_path))
    assert ok is True
    assert reason == ""


def test_validate_vault_path_flags_missing_dir(tmp_path):
    ok, reason = wiz._validate_vault_path(str(tmp_path / "does-not-exist"))
    assert ok is False
    assert "exist" in reason.lower()


def test_validate_vault_path_flags_non_vault(tmp_path):
    # exists but has no .obsidian/
    ok, reason = wiz._validate_vault_path(str(tmp_path))
    assert ok is False
    assert "obsidian" in reason.lower() or "vault" in reason.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/commands/test_wizard_memory_path_validation.py -v`
Expected: FAIL — `_validate_vault_path` does not exist.

- [ ] **Step 4: Implement the validator**

```python
def _validate_vault_path(path):
    """Return (is_ok, reason). ok if the dir exists and contains an .obsidian/ folder."""
    from pathlib import Path
    p = Path(path).expanduser()
    if not p.exists():
        return False, "that folder doesn't exist yet"
    if not (p / ".obsidian").is_dir():
        return False, "that folder isn't an Obsidian vault (no .obsidian/ inside)"
    return True, ""
```

- [ ] **Step 5: Wrap the path prompt in a validate/confirm loop**

In the obsidian branch, after `_path_input` returns `vault`, validate. If not ok AND interactive, warn and offer re-enter vs use-anyway:

```python
    while _can_interactive():
        ok, reason = _validate_vault_path(vault)
        if ok:
            break
        print(f"  {Color.YELLOW}⚠{Color.NC}  {reason}: {vault}")
        again = _radio_select(
            "What now?",
            [("Re-enter the path", "re"), ("Use it anyway", "use")],
            default=0, step=step, total=total, version=version,
        )
        if again == "use":
            break
        vault = _path_input(...)  # same prompt/args as the original call
```

When NOT interactive, skip the loop entirely (take `vault` as-is, as today). Then keep the existing `path = str(Path(vault) / subfolder)` join unchanged.

- [ ] **Step 6: Run the new tests + full suite**

Run: `uv run pytest tests/unit/commands/test_wizard_memory_path_validation.py tests/ -q` → PASS. Confirm existing memory/wizard tests still pass (the happy path uses a valid or non-interactive path).

- [ ] **Step 7: Commit**

```bash
git add agent_notes/commands/wizard/__init__.py tests/unit/commands/test_wizard_memory_path_validation.py
git commit -m "feat(wizard): validate the Obsidian vault path and offer re-enter on a bad path"
```

---

## Self-Review

**1. Requirement coverage.** #1 accept-all gate (one global prompt, default Yes, non-interactive → silent yes, DRY default via `_default_model_for_role`, claude-orchestrator skip preserved) and #2 path validation (exists + `.obsidian/`, warn + re-enter/use-anyway, non-interactive skips loop). Both keep `_select_*` signatures and `TOTAL_STEPS` unchanged.

**2. No placeholders.** Concrete code for helpers, gate, validator, and the loop. The one spot the coder must lift verbatim from existing code is the `_path_input(...)` argument list in Task 2 Step 5 — read the original call and reuse it exactly.

**3. Type consistency.** `_default_model_for_role(role, compatible) -> model`; `_select_accept_all_models(...) -> bool`; `_validate_vault_path(path) -> (bool, str)`. `_select_models_per_role` and `_select_memory` return types unchanged.

**Risk note.** The real risk is the happy-path functional test and the DRY requirement: accept-all=yes MUST equal accept-all=no-with-defaults (Task 1 Step 2's third test enforces this). If they diverge, the extraction in Step 4 wasn't used in both paths. Non-interactive regressions are guarded by "gate returns True when not interactive" + "validation loop is interactive-only."

## Execution Handoff

Subagent-driven: one coder for Task 1, review, one coder for Task 2, review, then full suite. No byte-identity gate (feature change). Live walkthrough happens later (user's step C).
