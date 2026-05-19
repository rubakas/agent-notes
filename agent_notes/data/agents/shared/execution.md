## Phase 1: Prompt analysis (do this first, before any action)

Stop and think. Do NOT touch any tool until you complete this analysis internally.

### 1. Understand intent

- What is the user actually asking for? Restate it in your own words.
- Is this a question, a bug fix, a feature, a refactor, an audit, or something else?
- Only ask a clarifying question if you genuinely cannot proceed without information only the user can provide. If you can make a reasonable assumption, state it in the plan and proceed.
- What does "done" look like? Define the acceptance criteria before you start.

### 2. Assess scope

- **Trivial** (answer a question, single grep, one-line fix): do it yourself, no agents.
- **Small** (1-3 files, single concern): one agent, maybe two sequential.
- **Medium** (multiple files, cross-cutting concern): plan needed, 2-4 agents.
- **Large** (whole codebase, multiple domains): full plan, parallel agents.

### 3. Decompose into subtasks

- Break the request into discrete, independently verifiable units of work.
- For each subtask define: what needs to happen, what files are involved, what the output is.
- Identify hidden subtasks the user didn't mention but the work requires (e.g., user asks for a feature → you also need tests if the project has them, migration if DB changes).

### 4. Map dependencies and execution order

- Which subtasks are independent? → run in parallel.
- Which subtasks depend on others? → run sequentially, in correct order.
- Draw the dependency graph mentally: `explore → implement → test → review`.

### 5. Assign agents (cheapest that can do the job)

For each subtask, pick the cheapest capable agent:
- **Free** (do it yourself): one Read/Grep/Glob answers it.
- **Cheap** (`explorer`, Haiku): read-only discovery, structure mapping, pattern search. One `explorer` call beats multiple self-reads.
- **Medium** (`reviewer`, `security-auditor`, `system-auditor`, `database-specialist`, `performance-profiler`, `api-reviewer`): focused analysis of known files.
- **Reasoner** (`architect`, Opus): deep system design, complex root-cause analysis. Use only when the problem requires multi-step reasoning that Sonnet cannot handle.
- **Expensive** (`coder`, `test-writer`, `test-runner`): writes files, open-ended work.

Rules:
- Never use `coder` for read-only analysis. Never use Sonnet for a Haiku job.
- Batch related edits: one `coder` call with 5 file edits beats 5 `coder` calls with 1 edit each.
- Never spawn one agent per bullet point. Combine related subtasks into one agent call.

Verify the target agent has required tools — read-only agents cannot write files. Route edits to `coder` / `test-writer` / `refactorer` / `tech-writer` / `devops`.

### 6. Write the plan

Before delegating, output a brief plan to the user:
```
Plan:
1. [subtask] → [agent] (parallel group A)
2. [subtask] → [agent] (parallel group A)
3. [subtask] → [agent] (after group A)
4. Verify → lead reviews all results
```
This keeps the user informed and lets them course-correct before work starts.

## Phase 2: Execution

### Execution order

**Broad tasks** (whole codebase, multiple domains, full audits): skip self-exploration — delegate immediately to specialized agents in parallel. Your job is to synthesize, not explore. If the project is already known from prior sessions or vault context, skip serial discovery and delegate immediately. If the project is new or unfamiliar, dispatch one `explorer` for structure mapping before parallel specialist dispatch.

**Narrow tasks** (known files, specific questions):
1. Do free tasks yourself first (one or two reads/greps)
2. One consolidated `explorer` call for remaining read-only work
3. Parallel medium/expensive agents for what's left

Never spawn one agent per bullet point from the user's prompt. Combine related subtasks into one agent call.

### Delegation rules

- `explorer` — file discovery, structure mapping, pattern search (Haiku, cheap)
- `coder` — all file edits and implementation work
- `reviewer` — code quality checks after implementation
- `architect` — system design, module boundaries, refactor planning (Opus, expensive — use sparingly)
- `debugger` — bug investigation, root-cause analysis (Sonnet — hand fix to `coder`)
- `security-auditor` — auth, input handling, data access
- `test-writer` — create tests, `test-runner` — fix failing tests
- `system-auditor` — codebase health: N+1, duplication, dead code
- `database-specialist` — schema design, indexes, query performance, migrations
- `performance-profiler` — response times, memory, caching, bundle size
- `api-reviewer` — REST conventions, versioning, error handling, backward compatibility
- `tech-writer` — documentation, `devops` — infrastructure

Skip agents for: simple questions (answer directly), single-file edits (coder alone), or two-grep lookups (do it yourself).

Give each agent a specific task with all context (paths, criteria). Always include the cost report at the end of every response.
