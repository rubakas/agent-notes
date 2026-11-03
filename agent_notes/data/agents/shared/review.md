## Phase 3: Review (after implementation, before verification)

After `coder` (or `test-writer`, `devops`) reports done, run a `reviewer` only when:
- the user asked for a review; or
- the diff is large: more than 300 changed lines by `git diff --shortstat` against the plan's base; or
- the diff touches auth, input handling, secrets or data access (then `security-auditor`), or schema and queries (then `database-specialist`).

Otherwise, run the tests and read the diff yourself, then move to Phase 4.

### 1. Analyze review findings yourself

Read the reviewer's output. For each finding, make your own judgment:
- **Agree**: include it in feedback to coder as-is.
- **Disagree**: drop it — not every reviewer suggestion is worth implementing. Explain why in your notes.
- **Escalate**: the finding reveals a deeper problem the reviewer didn't fully diagnose. Add your own analysis and a concrete fix direction.

Also add your own observations from reading the code that reviewers may have missed (architecture fit, consistency with other parts of the codebase, requirements misunderstanding).

### 2. Decide: approve or return

- **If no actionable findings**: approve, move to Phase 4.
- **If findings exist**: compile a single, prioritized feedback message and send it back to the same coder session. Include:
  - Which findings to fix (with your reasoning, not just the reviewer's words)
  - Your own additional comments
  - What NOT to change (to prevent scope creep)

### 3. Re-review only if needed

After coder addresses the feedback:
- If the changes were small/mechanical (rename, add a nil check): approve without re-review.
- If the changes were substantial (new logic, redesign): send to reviewer again.
- **Maximum 2 review rounds.** After that, approve what you have.
