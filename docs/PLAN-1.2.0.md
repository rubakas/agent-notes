# Release Plan — 1.2.0: Process Layer + Plugin Distribution

**Branch:** `release/1.2.0`
**Goal:** Borrow the best ideas from Superpowers (process discipline skills, slash commands,
SessionStart hook) and add a Claude Code plugin manifest for marketplace distribution.
**Current version:** 1.1.0
**Target version:** 1.2.0

---

## Context: Why these features

Superpowers (476k installs) has two things agent-notes lacks:

1. **Process discipline** — skills that enforce *how* to work (plan before coding, TDD,
   structured debugging). We have domain skills (Rails, Docker) but no methodology layer.
2. **Always-on context** — a `SessionStart` hook injects team context automatically.
   Right now, users must remember to invoke the lead agent; it doesn't self-activate.

Additionally: agent-notes has **zero discoverability** — no Claude Code plugin marketplace
listing. A `plugin.json` manifest fixes that.

---

## Tracks

| Track | Description | Priority |
|---|---|---|
| A | Process discipline skills | Must |
| B | Slash commands | Must |
| C | SessionStart hook | Must |
| D | Plugin manifest | Should |

Tracks A and B are independent and can be implemented in parallel.
Track C depends on knowing what the session context file contains (informed by Track A/B).
Track D depends on C (the hook config goes in plugin.json).

---

## Track A — Process Discipline Skills

### What to build

Five new skill directories under `agent_notes/data/skills/`. Each is a markdown file with
YAML frontmatter that the skill registry loads. The `group` field in frontmatter is used
by `registry.by_group()` → wizard auto-groups these under "Process" without code changes.

### File: `agent_notes/data/skills/plan-first/SKILL.md`

```markdown
---
name: plan-first
description: "Plan before coding: decompose, map dependencies, define acceptance criteria"
group: process
---

# Plan First

Before writing any code, produce a written plan the user can review.

## When to apply

Use this skill when the task involves more than one file, has unclear scope,
or when the user hasn't specified an implementation approach.

## Process

1. **Restate the goal** — one sentence. What does "done" look like?
2. **Decompose** — list every discrete subtask needed. Include hidden work
   (tests, migrations, type changes) the user didn't mention.
3. **Map dependencies** — which subtasks must happen before others?
   Mark parallel groups explicitly.
4. **Flag ambiguities** — list anything that needs a decision before work starts.
   Ask one clarifying question if critical information is missing.
5. **Present the plan** — show it to the user before touching any file.
   Wait for approval or correction.

## Output format

```
Plan:
1. [subtask] — [what changes, which files] (parallel group A)
2. [subtask] — [what changes, which files] (parallel group A)
3. [subtask] — [what changes, which files] (after group A)

Questions before starting:
- [ambiguity 1]
```

Do not begin implementation until the user approves the plan.
```

---

### File: `agent_notes/data/skills/test-driven/SKILL.md`

```markdown
---
name: test-driven
description: "RED-GREEN-REFACTOR: write failing test first, then implement, then clean up"
group: process
---

# Test-Driven Development

## The three rules

1. Write a failing test before writing any production code.
2. Write the minimum production code to make the test pass.
3. Refactor only when tests are green.

## Process

### RED — write a failing test
- Identify the smallest behavior to verify.
- Write the test. Run it. Confirm it fails for the right reason (not a syntax error,
  not a wrong import — the actual assertion must fail).
- Do not write production code yet.

### GREEN — make it pass
- Write the minimum code to pass the test. No extras.
- Run the test. Confirm it passes.
- If it still fails: diagnose the test failure before writing more code.

### REFACTOR — clean up
- Eliminate duplication.
- Improve naming.
- Extract helpers if clarity improves.
- Tests must stay green throughout refactor.

## When NOT to apply

- Exploratory spikes where you're learning the API.
- Tests that require extensive mocking that obscures the behavior being tested —
  in those cases, write an integration test first instead.

## Acceptance gate

A feature is not done until:
- All new tests pass.
- No existing tests regressed.
- No dead code or commented-out experiments remain.
```

---

### File: `agent_notes/data/skills/debugging-protocol/SKILL.md`

```markdown
---
name: debugging-protocol
description: "4-phase systematic debugging: instrument → evidence → hypothesis → fix"
group: process
---

# Debugging Protocol

Never guess. Never change code randomly. Follow the four phases.

## Phase 1 — Instrument

Add observability before forming any hypothesis:
- Add logging at the entry and exit of the failing code path.
- Log the inputs, intermediate values, and outputs.
- If a test is failing: read the full stack trace and error message before anything else.
- If a runtime error: reproduce it in isolation (smallest possible case).

Do not touch production logic in this phase.

## Phase 2 — Gather evidence

Run the instrumented version. Collect:
- Exact error message and location.
- What values are actually present vs. what was expected.
- The call stack at the point of failure.
- Any recent changes that correlate with when the bug appeared (`git log --oneline -20`).

## Phase 3 — Form a hypothesis

State the hypothesis explicitly:
> "I believe the bug is caused by X, because the evidence shows Y."

Test the hypothesis with the smallest possible change — ideally one that makes the bug
disappear in a controlled way (not a permanent fix yet). If the hypothesis is wrong,
return to Phase 2 with the new evidence.

## Phase 4 — Fix

Apply the minimal fix that addresses the root cause:
- Fix the root cause, not the symptom.
- Remove all instrumentation added in Phase 1.
- Run the full test suite.
- Confirm the original failure no longer reproduces.

## Escalation rule

If three hypothesis-fix cycles fail: stop and do an architectural review.
The bug likely indicates a deeper design assumption is wrong.
```

---

### File: `agent_notes/data/skills/brainstorming/SKILL.md`

```markdown
---
name: brainstorming
description: "Explore multiple approaches before committing — surface tradeoffs, then decide"
group: process
---

# Brainstorming

Use this skill when the problem has multiple valid solutions and the choice has
long-term consequences (API design, data model, architecture decision).

## Process

### 1. Generate options (diverge)

Produce at least three distinct approaches. For each:
- Name it (one noun phrase).
- Describe it in two sentences max.
- List the main advantage.
- List the main risk or cost.

Do not evaluate yet. Generate first.

### 2. Apply constraints (filter)

Filter options against the project's real constraints:
- Performance requirements
- Team familiarity
- Existing patterns in the codebase
- Timeline / scope

Eliminate options that violate hard constraints. Do not eliminate options just because
they're unfamiliar.

### 3. Recommend (converge)

Pick one option. State:
- Which option you recommend.
- Why it wins over the alternatives.
- What you're trading away (be honest about the downside).

Present the recommendation to the user. Do not begin implementation until they agree.

## Anti-patterns to avoid

- Generating only one option dressed up as brainstorming.
- Recommending the first option you thought of.
- Listing tradeoffs without actually comparing them.
```

---

### File: `agent_notes/data/skills/code-review/SKILL.md`

```markdown
---
name: code-review
description: "Systematic code review: correctness, safety, clarity, consistency"
group: process
---

# Code Review

When reviewing code, work through these four lenses in order. Report findings
grouped by lens, ranked by severity (blocking → suggestion).

## Lens 1 — Correctness

- Does the logic match the stated intent?
- Are edge cases handled (empty input, nil/None, off-by-one, concurrent access)?
- Are error paths handled and surfaced correctly?
- Do the tests cover the behavior, not just the happy path?

## Lens 2 — Safety

- Is user input validated at the system boundary?
- Are secrets, credentials, or PII handled safely (no logging, no exposure)?
- Are SQL queries parameterized?
- Are file paths sanitized before use?
- Does the change affect authentication or authorization logic?

## Lens 3 — Clarity

- Are names accurate? Does the name describe what the thing does, not how?
- Is control flow easy to follow? (Guard clauses over deep nesting.)
- Are comments present only where the "why" is non-obvious?
- Would a new team member understand this without asking?

## Lens 4 — Consistency

- Does this match the patterns already in the codebase?
- Does it follow project naming conventions (checked against existing files)?
- Does it introduce new abstractions or dependencies that already exist elsewhere?

## Output format

```
BLOCKING
- [file:line] [finding] — [why it matters]

SUGGESTIONS
- [file:line] [finding] — [optional: alternative]

APPROVED (if no blocking issues)
```

A BLOCKING finding must be resolved before merge. A SUGGESTION is optional.
```

---

### Wizard integration

No Python code changes needed. The wizard reads groups via `registry.by_group()`.
As long as each SKILL.md has `group: process` in frontmatter and the registry
loads it via the `group` field, the wizard automatically shows a "Process" group.

**Verify**: Check `agent_notes/registries/skill_registry.py` — confirm `by_group()`
reads the `group` frontmatter field. If the `Skill` domain object doesn't have a
`group` attribute yet, add it.

**Acceptance criteria:**
- `agent-notes list skills` shows all 5 new process skills.
- `agent-notes install` wizard shows a "Process" group alongside Rails, Docker, etc.
- All 5 SKILL.md files render correctly via `agent-notes build`.
- Tests: add `test_process_skills.py` — verify each skill loads, has correct group,
  correct frontmatter fields (name, description, group).

---

## Track B — Slash Commands

### What to build

Claude Code slash commands are `.md` files installed into `~/.claude/commands/`.
They appear as `/command-name` in Claude Code's command palette.

The installer already supports the `commands` component type
(`COMPONENT_TYPES = ("agents", "skills", "rules", "commands", "config")` in
`installer.py:46`). The `commands` layout key in `claude.yaml` is already `commands/`.

**What's missing**: a `data/commands/` source directory + build pipeline step to
copy it to `dist/claude/commands/`.

### Source files to create

#### `agent_notes/data/commands/plan.md`

```markdown
Break this task into a concrete plan before touching any code.

Use the plan-first skill:
1. Restate the goal in one sentence.
2. List every subtask with file paths and expected outputs.
3. Identify which subtasks are parallel vs. sequential.
4. Flag any ambiguities that need a decision.

Present the plan and wait for approval. Do not start implementing.
```

#### `agent_notes/data/commands/review.md`

```markdown
Review the current changes for correctness, safety, clarity, and consistency.

Use the code-review skill:
1. Run: git diff HEAD (or git diff --staged if reviewing staged changes).
2. Work through the four review lenses: correctness → safety → clarity → consistency.
3. Report BLOCKING findings and SUGGESTIONS separately.
4. If security-sensitive code is changed (auth, input handling, data access),
   apply security-auditor scrutiny.

Do not suggest cosmetic changes unless they create real ambiguity.
```

#### `agent_notes/data/commands/debug.md`

```markdown
Investigate and fix the reported bug using the debugging protocol.

Use the debugging-protocol skill:
1. Instrument — add logging to observe actual values (do not guess yet).
2. Gather evidence — run with instrumentation, collect exact error + stack.
3. Form a hypothesis — state it explicitly before changing anything.
4. Fix — apply the minimal change that addresses the root cause.

Remove all instrumentation after the fix. Run the full test suite.
```

#### `agent_notes/data/commands/brainstorm.md`

```markdown
Explore multiple approaches to this problem before committing to one.

Use the brainstorming skill:
1. Generate at least 3 distinct approaches (name + 2-sentence description + tradeoff each).
2. Filter against real project constraints.
3. Recommend one — state why it wins and what you're trading away.

Do not begin implementation until the user approves the chosen approach.
```

### Build pipeline change

**File to modify:** `agent_notes/commands/build.py`

Add a `copy_commands()` function (mirrors `copy_scripts()`):

```python
def copy_commands() -> list[Path]:
    """Copy command files from data/commands/ to dist/claude/commands/."""
    from ..config import DATA_DIR, DIST_DIR
    src = DATA_DIR / "commands"
    if not src.exists():
        return []
    dest = DIST_DIR / "claude" / "commands"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in src.glob("*.md"):
        out = dest / f.name
        shutil.copy2(f, out)
        copied.append(out)
    return copied
```

Call it in `build()`:
```python
print("Copying commands...")
command_files = copy_commands()
all_files = agent_files + global_files + skill_files + script_files + command_files
```

**Note:** Commands only apply to Claude Code (`claude.yaml` has `commands: commands/`).
OpenCode and Copilot have no commands layout key — the installer skips them already.

### Acceptance criteria

- `agent-notes build` produces `dist/claude/commands/{plan,review,debug,brainstorm}.md`.
- `agent-notes install` places those files in `~/.claude/commands/` (global scope)
  or `.claude/commands/` (local scope).
- In Claude Code: `/plan`, `/review`, `/debug`, `/brainstorm` appear in the
  command palette after install.
- Tests: extend `test_build.py` — verify `copy_commands()` produces the four files,
  verify they appear in `dist/claude/commands/`.

---

## Track C — SessionStart Hook

### What to build

A `SessionStart` hook that fires at the start of every Claude Code conversation and
injects a brief team roster + delegation reminder as additional context. This ensures
the lead agent pattern activates without the user having to remember to ask for it.

### How Claude Code hooks work

Claude Code reads hook configuration from `~/.claude/settings.json`. A `SessionStart`
hook runs a shell command; stdout is injected into the conversation as additional context.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cat ~/.claude/agent-notes-context.md 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

The hook simply cats a static file that the installer generates. This is intentionally
simple: no process spawning, no Python, no dependencies at session start.

### Files to create

#### `agent_notes/data/hooks/session-context.md.tpl`

This is the template for the injected context file. Variables substituted at install time:
`{{version}}`, `{{agents_list}}`, `{{installed_date}}`.

```markdown
<!-- agent-notes v{{version}} — injected at session start -->

## Your development team

You have a specialized agent team installed. Use them — don't try to do everything yourself.

**Delegation rules:**
- Analysis/exploration → `explorer` (fast, cheap, read-only)
- Implementation → `coder` (writes files)
- Review → `reviewer` + optionally `security-auditor`
- Debugging → `debugger` (investigate only) → `coder` (fix)
- Tests → `test-writer` (create) or `test-runner` (fix failing)
- Docs → `tech-writer`
- Infrastructure → `devops`

**When to use the lead pattern:**
For any task that touches more than 2 files or spans multiple concerns,
decompose with Phase 1 analysis before delegating. The lead pattern saves tokens
on large tasks by routing work to the cheapest capable agent.

**Available agents:** {{agents_list}}

Use `/plan` to plan before coding, `/review` to review changes,
`/debug` to debug systematically, `/brainstorm` to explore options.
```

#### `agent_notes/services/settings_writer.py` (new file)

Handles reading and merging `settings.json` without overwriting user configuration.

```python
"""Read, merge, and write Claude Code settings.json safely."""
import json
from pathlib import Path


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively. Lists are replaced, not extended."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def install_hook(settings_path: Path, hook_event: str, command: str) -> None:
    """Add or update a hook entry in settings.json without clobbering other settings."""
    data = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass  # treat corrupt file as empty

    hook_entry = {
        "hooks": {
            hook_event: [
                {"matcher": "", "hooks": [{"type": "command", "command": command}]}
            ]
        }
    }
    merged = _deep_merge(data, hook_entry)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(merged, indent=2) + "\n")


def remove_hook(settings_path: Path, hook_event: str, command: str) -> None:
    """Remove a specific hook entry from settings.json."""
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return
    hooks = data.get("hooks", {}).get(hook_event, [])
    cleaned = [
        entry for entry in hooks
        if not any(h.get("command") == command for h in entry.get("hooks", []))
    ]
    if cleaned:
        data["hooks"][hook_event] = cleaned
    elif "hooks" in data and hook_event in data["hooks"]:
        del data["hooks"][hook_event]
        if not data["hooks"]:
            del data["hooks"]
    settings_path.write_text(json.dumps(data, indent=2) + "\n")
```

### Installer integration

**File to modify:** `agent_notes/services/installer.py`

In `install_all()`, after placing agent/skill files, also:
1. Generate `~/.claude/agent-notes-context.md` from the template, substituting
   version and agent list from current state.
2. Call `settings_writer.install_hook(settings_path, "SessionStart", command)`.
3. For local scope: use `.claude/settings.json` and `.claude/agent-notes-context.md`.

In `uninstall_all()`, also:
1. Remove `agent-notes-context.md`.
2. Call `settings_writer.remove_hook(settings_path, "SessionStart", command)`.

**The command string to register:**
```
cat ~/.claude/agent-notes-context.md 2>/dev/null || true
```
(or the local-scope equivalent: `cat .claude/agent-notes-context.md 2>/dev/null || true`)

**Context file generation** — add to `agent_notes/services/session_context.py` (new file):

```python
"""Generate the session context file injected by the SessionStart hook."""
from pathlib import Path
from ..config import get_version


def render_context(agents: list[str], version: str = None) -> str:
    """Return the markdown content to write to agent-notes-context.md."""
    version = version or get_version()
    agents_list = ", ".join(sorted(agents)) if agents else "see ~/.claude/agents/"
    tpl_path = Path(__file__).parent.parent / "data" / "hooks" / "session-context.md.tpl"
    tpl = tpl_path.read_text()
    return (tpl
            .replace("{{version}}", version)
            .replace("{{agents_list}}", agents_list)
            .replace("{{installed_date}}", __import__('datetime').date.today().isoformat()))


def write_context(dest: Path, agents: list[str], version: str = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_context(agents, version))
```

### `agent-notes doctor` update

Add a check: verify `settings.json` exists and contains the hook entry.
If missing, report as fixable issue. `--fix` re-adds it.

**File to modify:** `agent_notes/commands/doctor.py` — add a `_check_session_hook()` function.

### Acceptance criteria

- After `agent-notes install`, `~/.claude/settings.json` contains the SessionStart hook.
- After `agent-notes install`, `~/.claude/agent-notes-context.md` exists and
  contains agent names and version.
- After `agent-notes uninstall`, both the hook entry and the context file are removed.
- `agent-notes doctor` reports the hook as missing if settings.json lacks it.
- `agent-notes doctor --fix` re-adds the hook if missing.
- `settings_writer.install_hook()` is idempotent (running twice doesn't duplicate the hook).
- `settings_writer` does not clobber unrelated settings.json keys.
- Tests: `test_session_hook.py` — cover install/uninstall/idempotent/corrupt-file cases.
  `test_settings_writer.py` — cover merge, remove, idempotent, corrupt-input cases.

---

## Track D — Plugin Manifest

### What to build

A `.claude-plugin/plugin.json` at the repo root makes agent-notes listable in the
Claude Code plugin marketplace. The plugin delivers a lightweight install path
(process skills + hook) without requiring the full Python wizard.

**Important:** Research the exact plugin.json schema from
`https://github.com/obra/superpowers/blob/main/.claude-plugin/plugin.json` before
implementing. The schema below is approximate based on Superpowers research.

### Files to create

#### `.claude-plugin/plugin.json`

```json
{
  "name": "agent-notes",
  "version": "1.2.0",
  "description": "Multi-agent team with cost-optimized model routing. 18 specialized agents, process discipline skills, and a structured lead-delegate-review workflow.",
  "author": "Eugene Naumov",
  "homepage": "https://github.com/rubakas/agent-notes",
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cat ~/.claude/agent-notes-context.md 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

#### `.claude-plugin/skills/`

Symlink or copy the 5 process discipline skills here so the plugin delivers them
without requiring a full Python install:
```
.claude-plugin/skills/
  plan-first/SKILL.md
  test-driven/SKILL.md
  debugging-protocol/SKILL.md
  brainstorming/SKILL.md
  code-review/SKILL.md
```

These skills work immediately after plugin install, with no wizard needed.

#### `.claude-plugin/README.md`

One-paragraph description for the marketplace listing.

### Plugin vs. full install relationship

| Feature | Plugin install | Full install (wizard) |
|---|---|---|
| Process skills | Yes | Yes (in "Process" group) |
| Domain skills (Rails, Docker) | No | Yes |
| Agent personas (18 agents) | No | Yes |
| Model routing (Opus/Sonnet/Haiku) | No | Yes |
| SessionStart hook | Yes (static context) | Yes (dynamic, lists installed agents) |
| Slash commands | No | Yes |

The plugin is the "try it" path. The full install is the power user path.
README should say: "For full agent team + model routing: `pip install agent-notes && agent-notes install`".

### Acceptance criteria

- `.claude-plugin/plugin.json` is valid JSON matching the Claude Code plugin schema.
- `.claude-plugin/skills/` contains all 5 process skills.
- Plugin can be installed locally via `/plugin install` in Claude Code (manual test).
- Process skills are accessible in Claude Code after plugin install.
- The hook fires at session start and outputs agent-notes context (requires the
  context file to exist — plugin install should create a default one).

---

## Execution order

```
Parallel group A:
  - Track A (process skills — pure data files, no code)
  - Track B (slash commands — data files + build.py copy_commands())

After group A:
  - Track C (session hook — needs agent list, integrates with installer)

After group A (independent of C):
  - Track D (plugin manifest — references process skills from Track A)

After all tracks:
  - Update VERSION to 1.2.0
  - Run full test suite (514+ tests, add ~20 new)
  - Manual smoke test: agent-notes install → verify all 4 tracks work end-to-end
```

---

## Files changed summary

| File | Change type | Track |
|---|---|---|
| `agent_notes/data/skills/plan-first/SKILL.md` | Create | A |
| `agent_notes/data/skills/test-driven/SKILL.md` | Create | A |
| `agent_notes/data/skills/debugging-protocol/SKILL.md` | Create | A |
| `agent_notes/data/skills/brainstorming/SKILL.md` | Create | A |
| `agent_notes/data/skills/code-review/SKILL.md` | Create | A |
| `agent_notes/registries/skill_registry.py` | Verify/modify `group` field support | A |
| `agent_notes/data/commands/plan.md` | Create | B |
| `agent_notes/data/commands/review.md` | Create | B |
| `agent_notes/data/commands/debug.md` | Create | B |
| `agent_notes/data/commands/brainstorm.md` | Create | B |
| `agent_notes/commands/build.py` | Add `copy_commands()`, call in `build()` | B |
| `agent_notes/data/hooks/session-context.md.tpl` | Create | C |
| `agent_notes/services/settings_writer.py` | Create | C |
| `agent_notes/services/session_context.py` | Create | C |
| `agent_notes/services/installer.py` | Add hook install/uninstall calls | C |
| `agent_notes/commands/doctor.py` | Add `_check_session_hook()` | C |
| `.claude-plugin/plugin.json` | Create | D |
| `.claude-plugin/skills/` | Create (5 files) | D |
| `agent_notes/VERSION` | Bump to 1.2.0 | Final |
| `tests/test_process_skills.py` | Create | A |
| `tests/test_build_commands.py` | Create | B |
| `tests/test_session_hook.py` | Create | C |
| `tests/test_settings_writer.py` | Create | C |

---

## Open questions before starting

1. **Skill registry `group` field**: Does `Skill` domain object have a `group`
   attribute? Does `by_group()` read it from SKILL.md frontmatter?
   Check `agent_notes/registries/skill_registry.py` and `agent_notes/domain/`.
   If not: add `group: str = "uncategorized"` to the `Skill` dataclass and parse it
   from frontmatter in the registry loader.

2. **Plugin.json schema**: Verify exact schema from Superpowers' plugin.json before
   writing ours. The `hooks` key structure may differ.

3. **Settings.json hook format**: Test on a real Claude Code install — does
   `SessionStart` with `matcher: ""` fire on every session? Or does matcher need
   to be omitted rather than empty string?

4. **Context file for plugin install**: When installed via plugin (no Python),
   the context file `~/.claude/agent-notes-context.md` won't exist. The hook
   uses `|| true` so it's safe, but the session will get no context. Consider
   bundling a default static context file in `.claude-plugin/` that the plugin
   copies to `~/.claude/` on install.
