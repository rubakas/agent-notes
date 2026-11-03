# chrome-test request template

The handoff prompt that Leg A step 5 writes to `request-<uuid>.md`. Fill in every resolved value before writing; no shell variables or angle-bracket tokens may survive into the file.

```text
## chrome-test handoff
Request-ID: <uuid>
Bus path: /Users/alice/.claude-work/chrome-test/myapp-9f86d081884c
Write your report to: /Users/alice/.claude-work/chrome-test/myapp-9f86d081884c/report-<uuid>.md
Write progress to: /Users/alice/.claude-work/chrome-test/myapp-9f86d081884c/progress-<uuid>.md
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
   Screenshot: save to /Users/alice/.claude-work/chrome-test/myapp-9f86d081884c/screenshots/<uuid>-scenario-1.png

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
Write report-<uuid>.md to: /Users/alice/.claude-work/chrome-test/myapp-9f86d081884c/report-<uuid>.md

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
