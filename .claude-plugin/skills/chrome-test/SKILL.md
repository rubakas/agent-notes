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

**Bus files (UUID-correlated for parallel requests):**

For each handoff, mint a short UUID and use three files in the bus dir:

| File | Writer | Purpose |
|------|--------|---------|
| `request-<uuid>.md` | dev session | scenarios + full handoff prompt |
| `progress-<uuid>.md` | chrome session | progress updates (NEW) |
| `report-<uuid>.md` | chrome session | PASS/FAIL results per scenario |

The `<uuid>` is an 8-character hex string that correlates all three files and allows multiple requests to coexist in parallel.

**UUID generation:**

```bash
# Preferred: uuidgen
REQUEST_ID=$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)

# Fallback if uuidgen is missing:
REQUEST_ID=$(python3 -c "import uuid;print(uuid.uuid4().hex[:8])")
```

Create the bus dir on demand: `mkdir -p "${BUS_DIR}"`.

---

## Three Invocation Modes

### Mode 1 — Live / Parallel (during iterative development)

Use when you want continuous browser feedback as code evolves. Multiple requests with different UUIDs can run in parallel on the same bus.

1. **Dev session** mints a new `<uuid>` and writes `request-<uuid>.md` to the bus with initial scenarios.
2. **Operator** starts ONE `claude --chrome` session manually — the dev session cannot launch it (it needs the real, visible Chrome). The dev session prints numbered operator instructions (see Leg A) with the request-file path to relay; the operator copies the one-line read command into the chrome session.
3. **Chrome session** reads `request-<uuid>.md`, runs scenarios, and writes progress to `progress-<uuid>.md` after each step.
4. **Dev session** polls for `report-<uuid>.md` via a background/scheduled check (run via `run_in_background` or a periodic wake-up — not a blocking foreground loop). While waiting, the lead may check `progress-<uuid>.md` to track a long run. Example check:
   ```bash
   # run this as a background or scheduled check, not inline
   test -f /absolute/path/to/bus/report-<uuid>.md && cat /absolute/path/to/bus/report-<uuid>.md
   ```
   The chrome session also relays completion verbally — the operator will say "report `<uuid>` ready" — at which point the dev session reads `report-<uuid>.md` directly from the bus (no paste-back).
5. On each report arrival, dev session triages failures, fixes, mints a NEW `<uuid>`, updates scenarios, and writes a new `request-<uuid>.md` — the loop continues with a fresh correlation id.

### Mode 2 — End-State Quality Check (default)

Use once — after linters and tests pass, before committing.

1. Dev session mints a `<uuid>`, generates scenarios, and writes `request-<uuid>.md` to the bus.
2. Operator follows the numbered instructions the dev session prints (see Leg A): opens a chrome session, copies in the one-line read command, and waits.
3. Chrome session runs scenarios, writes `report-<uuid>.md` to the bus automatically, then tells the operator to relay "report `<uuid>` ready" back to the dev session.
4. Dev session reads `report-<uuid>.md` directly from the bus when the operator relays the trigger, triages, fixes failures, optionally mints a NEW `<uuid>` and repeats for only the fixed scenarios.
5. All scenarios PASS → gate closes, commit proceeds.

**This is the mode the lead uses when the browser-test gate fires at the end of a frontend feature.**

### Mode 3 — Manual Ad-Hoc

User runs `/chrome-test` with a specific prompt (e.g., "check the login redirect").

1. Skill mints a `<uuid>` and generates a focused handoff prompt for the described scenario, writing it to `request-<uuid>.md`.
2. If a live chrome session is running on this bus, it picks it up automatically.
3. If no live session: skill prints the numbered operator instructions (see Leg A) with the request-file path and a reminder to start `claude --chrome`.
4. Ingest leg runs as normal when `report-<uuid>.md` appears.

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

**Before writing:** resolve the bus dir to a real absolute path (e.g. `/Users/alice/.claude-work/chrome-test/myapp`), mint a `<uuid>` (e.g. `a1b2c3d4`), and compute the TOTAL number of steps `N` across all scenarios. Substitute these into the block below. No shell variables (`${...}`) or angle-bracket tokens may survive into the file — the chrome session has no shell context.

Write the complete prompt (with all paths and the uuid resolved) to `<resolved-bus-dir>/request-<uuid>.md`.

```text
## chrome-test handoff
Request-ID: <uuid>
Bus path: /Users/alice/.claude-work/chrome-test/myapp
Write your report to: /Users/alice/.claude-work/chrome-test/myapp/report-<uuid>.md
Write progress to: /Users/alice/.claude-work/chrome-test/myapp/progress-<uuid>.md
Total steps: N

---

### PROGRESS PROTOCOL
After completing each step, overwrite progress-<uuid>.md with:

    X/N — Scenario <#>: <name> (step: <short description>)
Also print the same `X/N` progress line in chat so the operator watching the chrome session sees movement.

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
   Screenshot: save to /Users/alice/.claude-work/chrome-test/myapp/screenshots/<uuid>-scenario-1.png

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
Write report-<uuid>.md to: /Users/alice/.claude-work/chrome-test/myapp/report-<uuid>.md

Request-ID: <uuid>

**Scenario results:**
1. <name>: PASS|FAIL
   Expected: <from above>
   Observed: <what actually happened>
   Console errors: <verbatim or "none">
   Network errors: <verbatim or "none">
   Screenshot: <path or "none">

<!-- repeat per scenario -->

**Overall summary:** <one paragraph — what passed, what failed, anything surprising>

### WHEN DONE
1. Write your completed report to report-<uuid>.md at the path above automatically — do not wait to be asked.
2. Then print this for the operator:
   "Browser test <uuid> complete. Return to your first Claude session and say: report <uuid> ready."
```

Replace all occurrences of `/Users/alice/.claude-work/chrome-test/myapp`, `<uuid>`, and `N` with the real resolved values before writing.

After writing the file, print numbered operator instructions in chat (substitute the real resolved absolute path and real 8-char uuid — no `<uuid>` tokens or shell variables may survive into this output):

```
Browser test ready (a1b2c3d4). To run it:
1. Open a new terminal tab and start a chrome session:  claude --chrome
2. Copy/paste this line into that chrome session:
   Read and execute the browser test at /Users/alice/.claude-work/chrome-test/myapp/request-a1b2c3d4.md
3. When it finishes it will tell you to come back here — then say "report a1b2c3d4 ready" and I'll read the results.
```

That is the operator's only interaction with the dev session — the request file contains all further instructions for the chrome session.

---

## Leg B — Ingest (consume report-<uuid>.md)

### 1. Fetch the report

The dev session knows the `<uuid>` it minted. When the operator relays "report `<uuid>` ready" (or when a background/scheduled poll detects the file), read `report-<uuid>.md` directly from the bus — no paste-back needed. The chrome session writes it there automatically when done; consume it from the file, not from the operator's chat.

### 2. Parse

For each scenario, extract: PASS/FAIL, expected, observed, console errors, network errors, screenshot path.

### 3. Triage failures

For each FAIL:
- Reproduce locally using the exact steps from the scenario.
- Root-cause (apply the `debugging-protocol` skill).
- Fix.
- Re-verify: run relevant unit/integration tests; confirm locally before re-testing in browser.

### 4. Offer focused re-test

If failures were fixed and are UI-observable, offer a targeted re-handoff for only those scenarios. Mint a NEW `<uuid>`, write a new `request-<uuid>.md` to the same bus with those scenarios, and hand off by path (same as Leg A, step 5).

### 5. Surface surprises

Treat unexpected observations that are unrelated to the current feature as findings — surface them explicitly even if the scenario itself passed.

### 6. Summarize

Report: what failed, the fix applied, what passed, what (if anything) remains open.

---

## Gotchas

- The chrome session has NO memory of this dev session. The emitted prompt + bus path is the entire briefing — make it complete.
- `claude --chrome` drives the user's real visible Chrome/Edge and shares their logged-in browser state.
- JS modal dialogs (`alert` / `confirm` / `prompt`) freeze the chrome session — the operator must dismiss them by hand.
- Browser state does not auto-reset between runs — the handoff prompt must instruct the tester to start fresh.
- This is a community pattern, not an officially documented Anthropic workflow.
