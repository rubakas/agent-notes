---
name: chrome-test
description: Browser-test handoff via a profile-aware file bus between this dev session and a `claude --chrome` session. Use after frontend work is locally testable or on /chrome-test.
group: process
triggers:
  - chrome-test
  - browser test
  - browser-test handoff
  - test in browser
---

# chrome-test — Browser-Test Handoff

Coordinates browser testing between this dev session and a separate `claude --chrome` session via a profile-aware file bus. Two legs: **Generate** (write a handoff prompt + scenarios to the bus) and **Ingest** (consume the report the chrome session writes back).

---

## The File Bus

Resolve the base dir at runtime:

```
BUS_BASE=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
PROJECT_SLUG=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
BUS_DIR="${BUS_BASE}/chrome-test/${PROJECT_SLUG}"
```

This respects whichever Claude profile launched the session (personal `~/.claude`, work profile `~/.claude-work`, etc.). Do NOT read agent-notes state.json.

**Bus files:**

| File | Writer | Purpose |
|------|--------|---------|
| `request.md` | dev session | scenarios + full handoff prompt |
| `report.md` | chrome session | PASS/FAIL results per scenario |
| `run-id` | dev session | short correlation id (e.g. `abc1234-main`) |

Derive `run-id` from git short SHA + branch name: `$(git rev-parse --short HEAD)-$(git rev-parse --abbrev-ref HEAD)`. Use an incrementing counter (`run-001`, `run-002`, …) if git is unavailable.

Create the bus dir on demand: `mkdir -p "${BUS_DIR}"`.

---

## Three Invocation Modes

### Mode 1 — Live / Parallel (during iterative development)

Use when you want continuous browser feedback as code evolves.

1. **Dev session** writes `request.md` and `run-id` to the bus with initial scenarios.
2. **Operator** starts ONE `claude --chrome` session manually — the dev session cannot launch it (it needs the real, visible Chrome). Give the operator the bus path to paste in.
3. **Chrome session** watches the bus, runs scenarios, writes `report.md`.
4. **Dev session** polls for `report.md` via a background/scheduled check (run via `run_in_background` or a periodic wake-up — not a blocking foreground loop). Example check the lead runs on a schedule:
   ```bash
   # run this as a background or scheduled check, not inline
   test -f /absolute/path/to/bus/report.md && cat /absolute/path/to/bus/report.md
   ```
   Substitute the real resolved bus path. When `report.md` appears, the lead reads and triages it.
5. On each `report.md` arrival, dev session triages failures, fixes, updates `request.md` with revised/new scenarios and a new `run-id`, and the loop continues.

### Mode 2 — End-State Quality Check (default)

Use once — after linters and tests pass, before committing.

1. Dev session generates scenarios and writes them to the bus.
2. Operator pastes the handoff prompt into `claude --chrome`.
3. Chrome session writes one `report.md` to the absolute bus path.
4. Dev session reads `report.md`, triages, fixes failures, optionally repeats for only the fixed scenarios.
5. All scenarios PASS → gate closes, commit proceeds.

**This is the default mode the lead uses at end of a frontend feature.**

### Mode 3 — Manual Ad-Hoc

User runs `/chrome-test` with a specific prompt (e.g., "check the login redirect").

1. Skill generates a focused handoff prompt for the described scenario and writes it to `request.md`.
2. If a live chrome session is running on this bus, it picks it up automatically.
3. If no live session: skill prints the fenced handoff block for copy-paste, plus a reminder to start `claude --chrome` and paste the report back.
4. Ingest leg runs as normal when the report arrives.

---

## Leg A — Generate (produce the handoff prompt)

### 1. Gather context

```bash
git diff HEAD~1          # or git diff for uncommitted changes
git log --oneline -5
```

- Changed routes, views, controllers, components — list them.
- GH issue: infer number from branch name / recent commits (`gh issue view <n>`); ask only if genuinely unclear.
- UI entry points: every page/component the change touches.

### 2. Infer the local target

Check in order: `Procfile.dev`, `bin/dev`, `config/puma.rb`, `README`, framework default.

- Rails → `http://localhost:3000`
- Vite/Next.js → `http://localhost:5173` / `http://localhost:3000`
- Honor any `PORT=` overrides in worktrees.

### 3. Resolve credentials

Use ONLY documented, non-secret dev/seed credentials (e.g. `db/seeds.rb`, `README`). For anything unknown, use the placeholder `<<PASSWORD>>` and instruct the tester to ask the operator. **Never inline real secrets, tokens, or production credentials.**

### 4. Derive 2–5 concrete scenarios

For each scenario:
- **Steps**: exact paths, buttons, field values — no ambiguity.
- **Expected outcome**: concrete and observable — exact text, element state, redirect URL, error message.

Cover: happy path + key validation / edge cases for the changed area.

### 5. Emit the handoff prompt

**Before printing:** resolve the bus dir to a real absolute path (e.g. `/Users/alice/.claude-work/chrome-test/myapp`) and substitute it into every location reference in the block below. No shell variables (`${...}`) or angle-bracket tokens (`<BUS_DIR>`) may survive into the emitted prompt — the chrome session has no shell context.

Write the complete prompt (with all paths resolved) to `<resolved-bus-dir>/request.md` AND print it as ONE fenced `text` block in chat. The block must be fully self-contained.

```text
## chrome-test handoff
Run-ID: abc1234-main
Bus path: /Users/alice/.claude-work/chrome-test/myapp
Write your report to: /Users/alice/.claude-work/chrome-test/myapp/report.md

---

### APP / PRECONDITIONS
- URL: <inferred URL>
- Start command if not running: `<bin/dev or equivalent>`
- Login: <dev seed user email> / <<PASSWORD>> (ask operator if unsure)
- Fresh state: log out first / clear session cookies before each run

### WHAT CHANGED
<GH #NNN — issue title, or one-line summary>
<1–2 sentence description of what the feature does>

### TEST SCENARIOS

1. <Scenario name>
   Steps:
     1. Navigate to <path>
     2. <action>
     3. <action>
   Expect: <concrete observable outcome — exact text/state/redirect>
   Screenshot: save to /Users/alice/.claude-work/chrome-test/myapp/screenshots/abc1234-main-scenario-1.png

2. <Scenario name>
   ...

<!-- repeat for each scenario -->

### SAFETY RAILS
- STAY on <app origin> — do not navigate to external sites.
- HALT before: sending real email, calling paid external APIs, any irreversible action. Ask the operator first.
- Verify real UI state + screenshot as evidence. Never assume it worked.
- Browser state does NOT auto-reset between runs — start fresh (log out, clear state) as instructed.
- JS modal dialogs (alert/confirm/prompt) freeze this session — dismiss by hand if one appears.

### REPORT FORMAT
Write report.md to: /Users/alice/.claude-work/chrome-test/myapp/report.md

Run-ID: abc1234-main

**Scenario results:**
1. <name>: PASS|FAIL
   Expected: <from above>
   Observed: <what actually happened>
   Console errors: <verbatim or "none">
   Network errors: <verbatim or "none">
   Screenshot: <path or "none">

<!-- repeat per scenario -->

**Overall summary:** <one paragraph — what passed, what failed, anything surprising>
```

Replace all occurrences of `/Users/alice/.claude-work/chrome-test/myapp` and `abc1234-main` with the real resolved values before emitting.

After printing the block:
- Offer (don't assume) to copy via `pbcopy`.
- One-line reminder: "Paste into a separate `claude --chrome` session. Paste the report back here when done."

---

## Leg B — Ingest (consume report.md / pasted report)

### 1. Parse

For each scenario, extract: PASS/FAIL, expected, observed, console errors, network errors, screenshot path.

### 2. Triage failures

For each FAIL:
- Reproduce locally using the exact steps from the scenario.
- Root-cause (apply the `debugging-protocol` skill).
- Fix.
- Re-verify: run relevant unit/integration tests; confirm locally before re-testing in browser.

### 3. Offer focused re-test

If failures were fixed and are UI-observable, offer a targeted re-handoff for only those scenarios (new `run-id`, same bus).

### 4. Surface surprises

Treat unexpected observations that are unrelated to the current feature as findings — surface them explicitly even if the scenario itself passed.

### 5. Summarize

Report: what failed, the fix applied, what passed, what (if anything) remains open.

---

## Gotchas

- The chrome session has NO memory of this dev session. The emitted prompt + bus path is the entire briefing — make it complete.
- `claude --chrome` drives the user's real visible Chrome/Edge and shares their logged-in browser state.
- JS modal dialogs (`alert` / `confirm` / `prompt`) freeze the chrome session — the operator must dismiss them by hand.
- Browser state does not auto-reset between runs — the handoff prompt must instruct the tester to start fresh.
- This is a community pattern, not an officially documented Anthropic workflow.
