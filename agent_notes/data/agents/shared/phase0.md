## Phase 0 — Plan & Approval Gate (MANDATORY)

Before touching any tool that writes, edits, runs, installs, or otherwise has side effects, you MUST produce and get approval for a plan.

1. Restate the user's request in your own words. State the assumed acceptance criteria.
2. Decompose into discrete, independently verifiable subtasks. Identify dependencies.
3. If context is thin (you don't know what files are involved, what conventions apply, what tests exist), dispatch `explorer` first. Do not guess.
4. If a real ambiguity remains that only the user can resolve (priorities, tradeoffs, naming, scope), ask ONE focused clarifying question and stop. Do not invent answers.
5. Write the full plan to the user. Include:
   - Acceptance criteria (what "done" looks like)
   - Subtasks with assigned agents
   - Files that will be touched (paths)
   - How you'll verify each subtask
   - Risks and explicit out-of-scope items
6. Wait for explicit user approval. A "go", "yes", "ok", or "approved" counts. Silence does NOT count.
7. Only after approval, proceed to Phase 1 execution.

**Trivial-request exemption — narrow.** No plan needed for: (a) read-only responses — no Bash beyond `git status` / `git log` / `git diff` / `gh pr view` / `gh api`, no Edit / Write, no agent dispatch that writes files (factual questions, conversational replies, recall-from-memory, explicit one-shot reads); OR (b) purely mechanical one-line changes with no behavioral impact — typos, single config value changes, version bumps, formatting — where the diff touches no logic. Mechanical changes must be genuinely trivial: if there is any doubt about behavioral impact, require a plan.

Any task involving logic changes, or with words like "fix", "implement", "add", "refactor", "update", "build", "investigate" (which implies a follow-up fix), or that will dispatch `coder` / `test-writer` / `devops` / `refactorer` / `integrations` requires a written plan and explicit user approval before any side-effecting tool is touched, regardless of prompt brevity. A short prompt is not a trivial prompt.