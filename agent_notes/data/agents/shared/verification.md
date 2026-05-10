## Phase 4: Verification (do this before reporting done)

Never declare the task complete without verification. After all agents finish:

### 1. Review each agent's output (approve or reject)

For every agent result, make an explicit decision: **APPROVE** or **REJECT**.

- Did the agent do what was asked?
- Did it miss anything? Did it change things outside scope?
- Is the quality acceptable?

**If REJECT**: re-delegate to the **same agent session** (use `task_id` to resume) with what is wrong, what the expected output should look like, and only the correction (not the whole task).

**Maximum 2 rejection rounds per agent.** If still wrong after 2 attempts, do it yourself or reassign to a different agent.

### 2. Run tests (if code was changed)

- If the project has tests and any agent modified code, run the test suite now.
- Use a direct bash command for speed. Only escalate to `test-runner` if tests fail and need diagnosis.
- If tests fail due to agent changes → REJECT that agent's work with the failure output.

### 2.5 Resolve specialist conflicts

When specialist agents give contradictory recommendations: (1) `security-auditor` overrides `reviewer` on security-related code; (2) `database-specialist` overrides `reviewer` on query/schema decisions; (3) for all other conflicts, the lead decides based on the project's stated priorities.

### 3. Check cross-agent consistency

- If multiple agents touched related code, verify they don't conflict.
- Read the modified files yourself (free — just use Read tool).

### 4. Verify against the original request

- Re-read the user's original prompt. Does the combined result satisfy what they asked for?
- Check every acceptance criterion from Phase 1. All must be met.
- If anything is missing, loop back: re-delegate to coder → review again (Phase 3) → re-verify.
- If Phase 4 rejects committed changes, dispatch `coder` to create a `git revert` commit (not `reset --hard` or force-push).

Only after all checks pass and all agents are APPROVED, present the final result to the user.

### Post-phase self-check gate (multi-phase work only)

After completing each phase of multi-phase work, run a self-check before advancing:

1. Did the phase meet its stated acceptance criteria?
2. Did the phase introduce any new issues — test failures, diff drift, scope creep, broken invariants?
3. Was the output what was asked for, or only adjacent to it?

If any issue is found: treat it as a new task inside the CURRENT phase, fix it, then re-run the self-check. Do NOT advance to the next phase with open issues.

Each phase must leave the system in a verified-good state before the next begins. Single-task work (no phases) is exempt.
