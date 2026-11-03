# Official docs digest (collected 2026-10-30 by a claude-code-guide agent)

Caveats from the collecting agent:
- Quotes come from WebFetch extraction, not raw HTML. Re-fetch any value before you enforce it in a finding.
- CHANGELOG: only 2.1.300–2.1.314 were reachable, without dates. The other version stamps come from the doc pages.
- NOT FOUND: the built-in subagent table (Explore/Plan/general-purpose), the agent-teams page, and file-based subagent returns.

## 1. Skills — https://code.claude.com/docs/en/skills.md

**How frontmatter is read**
- Every field is optional; `description` is "recommended".
- Unknown fields are ignored.
- Frontmatter is read only when the opening `---` is on line 1. Malformed YAML loads the skill with no fields set.

**Claude Code fields**

| Field | What it does |
|---|---|
| `name` | Defaults to the directory name. |
| `description` | What the skill does and when to use it. |
| `when_to_use` | Appended to the description. Together they are cut at 1,536 characters in the listing. |
| `argument-hint` | Hint shown for arguments. |
| `arguments` | Named positional arguments. |
| `disable-model-invocation` | Default false. |
| `user-invocable` | Default true; false hides the skill from the `/` menu. |
| `allowed-tools` | Grant for the invoking turn only. It clears on the next user message. |
| `disallowed-tools` | Tools removed while the skill is active. |
| `model` | Applies for the rest of the turn. |
| `effort` | `low`, `medium`, `high`, `xhigh` or `max`, for the turn. |
| `context: fork` | Runs the skill in a forked subagent. |
| `agent` | Subagent type to use with `context: fork`. |
| `background` | Used with fork; default true. |
| `hooks` | Hooks for the skill. |
| `paths` | Glob patterns that limit automatic loading. |
| `shell` | `bash` or `powershell`. |
| `metadata`, `license`, `compatibility` | Accepted but ignored by Claude Code. |

**Outside Claude Code** (claude.ai upload, Skills API, `package_skill.py`)
- Only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools` are allowed. "Any other key causes a hard error."

**Open standard** — https://agentskills.io/specification
- `name`: 1–64 characters, lowercase letters, digits and hyphens, no leading, trailing or double hyphens. It must match the parent directory.
- `description`: 1–1024 characters, saying what the skill does and when to use it.
- `license`; `compatibility` (≤500 characters); `metadata` (a string-to-string map); `allowed-tools` (experimental).

**Platform best practices** — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- The name must not contain `anthropic` or `claude`. Neither name nor description may contain XML tags.

**Description budget**
- The listing budget is 1% of the context window. On overflow, descriptions of the least-invoked skills are dropped first; names always stay.
- Settings that change it: `skillListingBudgetFraction`, `SLASH_COMMAND_TOOL_CHAR_BUDGET`, `skillListingMaxDescChars`, and `skillOverrides` ("name-only").
- Put the key use case first.
- `/doctor` estimates the listing cost. `/skill-doctor` finds unused skills.

**Substitutions**
- `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N` and `$name`.
- `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`, `${CLAUDE_SKILL_DIR}` and `${CLAUDE_PROJECT_DIR}`.
- Write `\$` for a literal dollar sign.

**`!` shell preprocessing**
- Inline `` !`cmd` `` or a ```` ```! ```` fence.
- A failing command aborts the invocation. Timeout is 2 minutes.
- `disableSkillShellExecution` turns it off. It never runs in synced claude.ai skills (v2.1.228+).

**Size**
- Keep SKILL.md under 500 lines and the body concise; it stays in context across turns.
- References go one level deep.
- A reference over 100 lines needs a table of contents.
- Use forward slashes in paths.
- Refer to MCP tools as `ServerName:tool_name` (platform page).
- The body should be under 5000 tokens (agentskills.io).

**Authoring checklist** — platform best-practices page
- Write in the third person. Say what the skill does and when to use it, with trigger terms.
- Gerund names are suggested. Avoid helper, utils, tools, documents, data and files.
- Match the degree of freedom to the task: prose for high freedom, scripts for low.
- Build evaluations first, at least 3, and test with Haiku, Sonnet and Opus.
- Avoid time-sensitive content; use an "old patterns" section instead.
- Avoid offering too many options: give a default plus an escape hatch.
- Scripts should handle their own errors. No voodoo constants.

**Version notes**

| Version | Change |
|---|---|
| v2.1.196 | `/context` skills row semantics changed. |
| v2.1.228 | Synced-skill restrictions. |
| v2.1.260 | `skillOverrides` aliases. |
| v2.1.280 | `manifest.json` in `~/.claude/skills/` no longer moves folders to trash. |
| v2.1.283 | `/doctor prompt-audit`. |
| v2.1.286 | Skills named `verify` or `simplify` run before commits. |
| v2.1.304 | Per-source cap on skill hooks; `/reload-skills` sends only changed skills. |

## 2. Subagents — https://code.claude.com/docs/en/sub-agents.md

**Frontmatter**
- Only `name` and `description` are required. Field names are camelCase. Unknown fields are ignored silently.

| Field | What it does |
|---|---|
| `name` | Up to 256 characters, no `:`. |
| `description` | When Claude should delegate. "use proactively" is the documented phrase. Over 15,000 tokens of descriptions in total gives a warning. |
| `tools` | Allowlist. Omit it to inherit. Use `skills`, not `Skill`, to preload skills. |
| `disallowedTools` | Denylist, applied first. |
| `model` | `sonnet`, `opus`, `haiku`, `fable`, a full ID (e.g. `claude-opus-5-5`) or `inherit`. |
| `permissionMode` | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan`, `manual`. Ignored for plugin agents. |
| `maxTurns` | Partial output plus resumable at the limit (v2.1.246+). |
| `autoCompactWindow` | An integer from 100000 to 1000000 (v2.1.296+). |
| `skills` | Preloads up to 32. A skill with disable-model-invocation can't be preloaded. |
| `mcpServers` | MCP servers for the agent. |
| `hooks` | `Stop` becomes `SubagentStop` at runtime. |
| `memory` | `user` → `~/.claude/agent-memory/<name>/`; `project` → `.claude/agent-memory/<name>/` (the recommended default); `local` → `.claude/agent-memory-local/<name>/`. Turning it on adds Read, Write and Edit automatically. |
| `background` | `true` forces background. |
| `omitClaudeMd` | Skips CLAUDE.md (v2.1.271+). |
| `effort` | `low` … `max`. `CLAUDE_CODE_EFFORT_LEVEL` overrides it. |
| `isolation` | `worktree` only. |
| `color` | red, blue, green, yellow, purple, orange, pink or cyan. |
| `initialPrompt` | Used only when the agent runs as the main agent. |
| `experimental.cacheTtl` | `5m` or `1h`. |

**Model resolution**, in order:
1. the per-invocation parameter (aliases only);
2. the frontmatter;
3. the `CLAUDE_CODE_SUBAGENT_MODEL` env var;
4. the main model.

A family alias resolves to the main model when the main model is in the same family.

**Tools**
- MCP: `mcp__server__*`. A server name that contains `__` needs the full name plus `__*`.
- `disallowedTools: Bash(git push *)` removes the WHOLE Bash tool. Use permissions deny rules instead.
- Removed even when listed: `Agent` (at the depth limit), `AskUserQuestion`, `EnterPlanMode`, `ExitPlanMode`, `ScheduleWakeup`, `Workflow`, …
- Background subagents get a reduced built-in set: Read, Grep, Glob, LSP, Bash, Edit, Write, NotebookEdit, WebFetch, WebSearch, TodoWrite, Skill, ToolSearch, Monitor, SendMessage, Artifact, … plus all MCP tools.
- `Agent(type)` allowlists work only on the main thread (`--agent`).

**Nesting and concurrency**
- Subagents CAN spawn subagents, up to 3 layers (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; 1 disables nesting).
- The concurrency cap defaults to 20 (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, v2.1.217+).

**Results**
- A subagent returns a text summary. A background subagent's result arrives in a completion notification.
- Final reports are scanned for instruction-shaped text, which gets a marker but is not removed.

**Foreground and background**
- Foreground blocks the main session, and permission prompts pass through to the user.
- In the background, prompts surface in the main session and name the subagent.
- From v2.1.302, desktop and VS Code run subagents in the background by default (fork mode). `claude -p` and the SDK run them in the foreground.
- If the main session is in bypassPermissions, acceptEdits or auto mode, the subagent inherits that mode and its own `permissionMode` is ignored.

**What a subagent loads**
- Its own system prompt (not Claude Code's), the task, the CLAUDE.md hierarchy, a git status snapshot, preloaded skills and the sibling roster. Explore and Plan skip CLAUDE.md and git status.
- It does NOT get the main session's auto memory or output style.
- Explore and Plan are one-shot (not resumable). Use general-purpose or a custom agent to continue work.

**Version notes**

| Version | Change |
|---|---|
| v2.1.63 | Task renamed to Agent; `Task(...)` alias kept. |
| v2.1.300 | Agent hooks resolve model aliases. |
| v2.1.302 | Fork mode is the default; at most 12 hooks of one event run at once. |
| v2.1.304 | Resumed subagents keep their recent work. |

## 3. Memory and rules — https://code.claude.com/docs/en/memory.md

**CLAUDE.md**
- Load order: managed → user `~/.claude/CLAUDE.md` → project `./CLAUDE.md` or `./.claude/CLAUDE.md` → `CLAUDE.local.md`. The files are concatenated, not overridden.
- Files in subdirectories load on demand.
- AGENTS.md is read only when no CLAUDE.md exists (v2.1.277+).

**Size**
- Aim for under 200 lines per CLAUDE.md.
- On-demand files have a per-file character limit: 40,000 characters on a 200K context, 150,000 on later 1M models (enforced from v2.1.309).
- Files over 4 MiB are skipped.
- HTML comments are stripped.

**`/doctor prompt-audit`** (v2.1.283+)
- It audits CLAUDE.md, rules, skills and subagents under `.claude/` and `~/.claude/` for instructions "written for older models" and for contradictions.

**`@` imports**
- Paths are relative to the importing file, with up to 4 hops.
- Imports are not parsed inside backticks or code fences.
- Imports do not save context.
- A file outside the working directory needs one-time approval.

**`.claude/rules/*.md`** (project) and `~/.claude/rules/` (user, loaded first)
- A rule without `paths` loads at launch.
- "`paths` is the only field Claude Code reads from a rule."
- A path-scoped rule loads when Read, Write or Edit touches a matching file.

**Auto memory**
- Lives in `~/.claude/projects/<project>/memory/`.
- The first 200 lines or 25KB of `MEMORY.md` load each session.
- Types: user, feedback, project, reference.
- Subagents do not get it (except forks).

**How CLAUDE.md is delivered**
- It arrives as a user message after the system prompt, and is treated as context, not enforced config. Use hooks for guarantees.

## 4. Prompting current models

**General** — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Replace "CRITICAL: You MUST use this tool when…" with "Use this tool when…". Remove over-prompting; "If in doubt, use [tool]" causes overtriggering.
- Use effort as the fallback lever.
- Latest models orchestrate subagents natively. Opus 5 "delegates to subagents more readily than prior models."
- Use subagents for parallel, isolated or independent workstreams. For simple tasks, sequential operations and single-file edits, work directly.
- Replace blanket defaults with targeted instructions.
- Tune anti-laziness prompting, since newer models overtrigger on it.

**Opus 5** — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
- Over-verification: remove explicit "verify / double-check" instructions; they cause over-verification.
- Opus 5 can expand scope. Sample prompt: "Deliver what was asked, at the scope intended."
- Subagent cap (sample): "Delegate to a subagent only for large tasks that are genuinely independent and parallelizable… Do not delegate work you can finish yourself in a handful of tool calls… keep spawn counts low."
- "set deterministic caps on how many agents can be launched": `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, SDK `max_budget_usd`.
- Claude Code adds its own delegation instruction only with the claude_code system-prompt preset.
- Keep responses focused. Match document length to the task. Avoid "double-check your answer".

**Opus 5.5** — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
- Default effort is medium (Opus 5 was high). Reserve xhigh and max for measured gains.
- Literal filtering: "only report high-severity issues" may make it report less. Ask for everything, then filter in a separate pass.
- Unattended runs: a text-only end_turn is a report, not completion. Keep a checklist.

**Sonnet 5.5** — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
- Agentic coding: start at medium. At low or medium it is more likely to stop and check in.
- Scope sample: "Don't add features, tests, files, docs or refactors that weren't asked for."
- Reviewer subagents at max effort: the sample "don't launch reviewer sub-agents unless the user asked for a review" cut cost by about a third.
- At low effort it may skip verification.

**Haiku 5.5** — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5
- Default effort is medium. At low, in long agent prompts, it may skip a search, stop early or skip a check.
- Search nudge: "Your training data ends well before today's date…". Avoid blanket "search for every factual question" instructions.

**Fable 5.1** — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1
- Default effort is high. At medium it is about Fable 5 quality for less cost.
- It writes fewer progress updates; ask for them.
- Batch independent tool calls.
- Finish the whole task: "Want me to…?" blocks work.
- Scope is the deliverable: don't quietly narrow, widen or swap it.
- Let the lead keep working while subagents run.
- It uses less bold and fewer headers. Replace anti-formatting language with a rule for when to format.
- Prefer targeted edits over whole-file rewrites.
- Compaction: list what to preserve.
