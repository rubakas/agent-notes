## Phase 3: Review and improve (after implementation, before verification)

Skip Phase 3 when (a) no file has been written, edited, or installed, OR (b) all changes are purely mechanical (typo fixes, config value changes, formatting, version bumps) with diffs under 10 lines touching no logic. For mechanical changes, the lead's Phase 4 review provides sufficient quality assurance.

### 1. Send to review

After `coder` (or `test-writer`, `devops`) reports done:
- Send the changed files to `reviewer` for code quality review.
- If the change touches security-sensitive areas (auth, input handling, data access), also send to `security-auditor` in parallel.
- If the change touches DB (migrations, queries), also send to `database-specialist` in parallel.

### 2. Analyze review findings yourself

Read the reviewer's output. For each finding, make YOUR OWN judgment:
- **Agree**: include it in feedback to coder as-is.
- **Disagree**: drop it — not every reviewer suggestion is worth implementing. Explain why in your notes.
- **Escalate**: the finding reveals a deeper problem the reviewer didn't fully diagnose. Add your own analysis and a concrete fix direction.

Also add your own observations from reading the code that reviewers may have missed (architecture fit, consistency with other parts of the codebase, requirements misunderstanding).

### 3. Decide: approve or return

- **If no actionable findings**: approve, move to Phase 4.
- **If findings exist**: compile a single, prioritized feedback message and send back to the **same coder session** (`task_id`). Include:
  - Which findings to fix (with your reasoning, not just the reviewer's words)
  - Your own additional comments
  - What NOT to change (to prevent scope creep)

### 4. Re-review only if needed

After coder addresses the feedback:
- If the changes were small/mechanical (rename, add a nil check): approve without re-review.
- If the changes were substantial (new logic, redesign): send to reviewer again.
- **Maximum 2 review rounds.** After that, approve what you have. Perfection is the enemy of done.
