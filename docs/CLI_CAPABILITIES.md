# CLI Capabilities Catalogue

**Purpose:** Source of truth for what each supported CLI can do. Used by the agent-notes engine to generate correct configs per CLI.

**Last researched:** 2026-04-22
**Sources:** Official Claude Code and OpenCode documentation fetched directly from docs.claude.com and opencode.ai

---

## Claude Code

### Installation paths

- **Global home**: `~/.claude/`
- **Local**: `.claude/`
- **Config file (global)**: `~/.claude/CLAUDE.md`
- **Config file (local)**: `.claude/CLAUDE.md` or `CLAUDE.md` at project root
- **Settings (global)**: `~/.claude/settings.json`
- **Settings (project)**: `.claude/settings.json`
- **Settings (project local, gitignored)**: `.claude/settings.local.json`
- **Managed settings (macOS)**: `/Library/Application Support/ClaudeCode/managed-settings.json` or drop-in directory `/Library/Application Support/ClaudeCode/managed-settings.d/`
- **Managed settings (Linux/WSL)**: `/etc/claude-code/managed-settings.json` or drop-in directory `/etc/claude-code/managed-settings.d/`
- **Managed settings (Windows)**: `C:\Program Files\ClaudeCode\managed-settings.json` or drop-in directory `C:\Program Files\ClaudeCode\managed-settings.d/`
- **Managed settings (Windows user-level, lower priority)**: `HKCU\SOFTWARE\Policies\ClaudeCode` (registry)
- **MDM managed preferences (macOS)**: `com.anthropic.claudecode` managed preferences domain via `.mobileconfig` configuration profiles (Jamf, Kandji, Iru, etc.)
- **Other configuration**: `~/.claude.json` (preferences, OAuth session, per-project state, MCP servers, caches)
- **Project MCP servers**: `.mcp.json` at project root

**Sources:**
- https://docs.claude.com/en/docs/claude-code/settings (Configuration scopes, Settings files, Available scopes, How scopes interact)

---

### Agents (sub-agents)

- **Location (global)**: `~/.claude/agents/<name>.md`
- **Location (project)**: `.claude/agents/<name>.md`
- **Discovery**: Agents discovered by walking up from current working directory; directories added with `--add-dir` grant file access only, not agent configuration discovery
- **Markdown format**: YAML frontmatter between `---` markers + markdown body (system prompt)
- **Session start**: Agents are loaded at session start; creating a subagent by manually adding a file requires session restart or use of `/agents` command to load immediately

#### Frontmatter fields (all optional except noted)

| Field | Required | Type | Default | Description |
|-------|----------|------|---------|-------------|
| `name` | No | string | Directory name | Unique identifier using lowercase letters and hyphens (max 64 characters) |
| `description` | **Yes** | string | First paragraph of markdown if omitted | When Claude should delegate to this subagent; used for automatic delegation decision |
| `model` | No | string | `inherit` | Model to use: `sonnet`, `opus`, `haiku`, a full model ID (e.g., `claude-opus-4-7`, `claude-sonnet-4-6`), or `inherit` to use parent |
| `tools` | No | string or list | Inherit all | Tools the subagent can use; comma-separated or YAML list. Inherits all tools from parent if omitted |
| `disallowedTools` | No | string or list | None | Tools to deny, removed from inherited or specified list |
| `permissionMode` | No | string | `default` | One of: `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | No | integer | Unlimited | Maximum number of agentic turns before agent stops |
| `skills` | No | list | None | Skill names to preload into subagent context at startup (full skill content injected, not just made available for invocation) |
| `mcpServers` | No | object | None | MCP servers available to this subagent. Each entry is either a server name string (referencing pre-configured server) or inline definition with server name as key and full MCP config as value |
| `hooks` | No | object | None | Lifecycle hooks scoped to this subagent; fires when subagent is spawned as subagent or runs as main session |
| `memory` | No | string | None | Persistent memory scope: `user` (`~/.claude/agent-memory/<name>/`), `project` (`.claude/agent-memory/<name>/`), or `local` (`.claude/agent-memory-local/<name>/`) |
| `background` | No | boolean | `false` | Set to `true` to always run this subagent as a background task |
| `effort` | No | string | Inherit from session | Effort level when this subagent is active. Options: `low`, `medium`, `high`, `xhigh`, `max` (available levels depend on model) |
| `isolation` | No | string | None | Set to `worktree` to run in temporary git worktree, giving isolated copy of repository |
| `color` | No | string | None | Display color: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |
| `initialPrompt` | No | string | None | Auto-submitted as first user turn when agent runs as main session agent via `--agent` or `agent` setting |

#### Prompt body

- Everything after the closing `---` of frontmatter becomes the system prompt
- Markdown format
- Receives only this system prompt (plus basic environment details like working directory), not full Claude Code system prompt
- Subagent starts in main conversation's current working directory

#### Memory

- **Mechanism**: `## Memory` section is **NOT** a dedicated mechanism; memory is handled via `memory:` frontmatter field
- **Auto memory**: Built-in auto memory stores to `~/.claude/agent-memory/<agent-name>/MEMORY.md` (if `memory: user` set) or `.claude/agent-memory/<agent-name>/MEMORY.md` (if `memory: project`)
- **Cross-session**: Memory survives across conversations for same agent
- **Instructions in subagent**: System prompt should include instructions for reading/writing memory; first 200 lines or 25KB of `MEMORY.md` loaded at startup

#### Built-in subagents (cannot be customized directly but can be overridden)

| Name | Model | Tools | Purpose |
|------|-------|-------|---------|
| `Explore` | Haiku (fast, low-latency) | Read-only (no Write/Edit) | File discovery, code search, codebase exploration |
| `Plan` | Inherits from main | Read-only (no Write/Edit) | Research for planning, gather context before presenting plan |
| `general-purpose` | Inherits from main | All tools | Complex research, multi-step operations, code modifications |
| `statusline-setup` | Sonnet | All | Internal: when user runs `/statusline` |
| `Claude Code Guide` | Haiku | All | Internal: answers questions about Claude Code features |

#### Choosing subagent scope

- **Managed settings** (highest priority): Deployed via managed settings, take precedence
- **`--agents` CLI flag**: Session-only, passed as JSON
- **`.claude/agents/`**: Project-specific, checked into repo, shared with team
- **`~/.claude/agents/`**: Personal, available in all projects
- **Plugin agents**: Bundled with plugins; appear with `plugin-name:agent-name` namespace (no `hooks`, `mcpServers`, or `permissionMode` support in plugin agents)

#### Tool access in subagents

- Default: Subagents inherit all tools from parent
- `tools` field: Allowlist specific tools (if set, inherits nothing else unless explicitly listed)
- `disallowedTools` field: Denylist tools (applied first if both fields present)
- `Agent(agent-type)` syntax: Restrict which subagents can be spawned via Agent tool; e.g., `Agent(worker, researcher)` allows only those two; `Agent` alone allows any; omitted blocks all

#### Permission modes for subagents

| Mode | Behavior |
|------|----------|
| `default` | Standard permission checking with prompts |
| `acceptEdits` | Auto-accept file edits and common filesystem commands for working directory paths |
| `auto` | Auto mode classifier reviews commands; protected-directory writes prompt |
| `dontAsk` | Auto-deny permission prompts (allowed tools still work) |
| `bypassPermissions` | Skip permission prompts (except `.git`, `.claude`, `.vscode`, `.idea`, `.husky` which still prompt unless they're `.claude/commands`, `.claude/agents`, `.claude/skills`) |
| `plan` | Plan mode (read-only exploration) |

**Note**: If parent uses `bypassPermissions` or `acceptEdits`, takes precedence; subagent mode in frontmatter ignored. If parent uses auto mode, subagent inherits and frontmatter `permissionMode` ignored.

#### Subagent isolation

- **Default**: Subagent starts in main conversation's CWD; `cd` commands don't persist between tool calls within subagent
- **`isolation: worktree`**: Subagent receives isolated copy of repository in temporary git worktree; automatically cleaned up if subagent makes no changes

#### Viewing subagents

- **In session**: `/agents` command opens tabbed interface
- **From CLI**: `claude agents` lists all configured subagents (shows built-in, user, project, plugin, overrides)
- **Permission restrictions**: `Agent(subagent-name)` syntax in permissions; can use `permissions.deny: ["Agent(Explore)"]` to block specific subagents

**Sources:**
- https://docs.claude.com/en/docs/claude-code/sub-agents (complete agent configuration, frontmatter, built-in agents, scopes, tool access, memory, examples)

---

### Skills

- **Location (global)**: `~/.claude/skills/<skill-name>/SKILL.md`
- **Location (project)**: `.claude/skills/<skill-name>/SKILL.md`
- **Directory-based**: Each skill is a directory with `SKILL.md` as required entrypoint
- **Supporting files**: Optional files in skill directory (templates, examples, scripts, reference docs) can be referenced from `SKILL.md`
- **Live change detection**: Changes to skills under `~/.claude/skills/`, `.claude/skills/`, or `--add-dir` directories take effect within current session without restart (only if directory existed at session start)
- **Nested discovery**: Claude Code automatically discovers skills from nested `.claude/skills/` directories (e.g., `packages/frontend/.claude/skills/` when editing files in that package)
- **From additional directories**: Skills in `--add-dir` directories' `.claude/skills/` load automatically (exception to general rule that `--add-dir` grants file access only)

#### SKILL.md format

- **Frontmatter**: YAML between `---` markers (optional; only `description` recommended)
- **Body**: Markdown content (instructions, templates, details)

#### Frontmatter fields (all optional)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name; defaults to directory name if omitted. Lowercase letters, numbers, hyphens only (max 64 characters) |
| `description` | string | What the skill does and when to use it. Claude uses this for automatic invocation decision. Combined with `when_to_use`, truncated at 1,536 characters. If omitted, uses first paragraph of markdown |
| `when_to_use` | string | Additional trigger context, appended to `description` in skill listing |
| `argument-hint` | string | Hint shown during autocomplete (e.g., `[issue-number]` or `[filename] [format]`) |
| `arguments` | string or list | Named positional arguments for `$name` substitution. Space-separated string or YAML list. Names map to positions in order |
| `disable-model-invocation` | boolean | If `true`, only user can invoke with `/skill-name`; Claude cannot invoke automatically. Prevents skill from being preloaded into subagents |
| `user-invocable` | boolean | If `false`, hidden from `/` menu; only Claude can invoke automatically |
| `allowed-tools` | string or list | Tools granted permission without approval when skill active (doesn't restrict other tools; permissions still govern baseline) |
| `model` | string | Model override for skill execution. Accepts `/model` values or `inherit`. Default inherits session model |
| `effort` | string | Effort level override. Options: `low`, `medium`, `high`, `xhigh`, `max` (depends on model) |
| `context` | string | Set to `fork` to run in isolated subagent context |
| `agent` | string | Which subagent type to use when `context: fork` is set. Options: built-in (`Explore`, `Plan`, `general-purpose`) or custom agent name. Default `general-purpose` |
| `hooks` | object | Lifecycle hooks scoped to skill (fire only while skill active) |
| `paths` | string or list | Glob patterns to restrict when skill activates. Claude loads skill automatically only when working with files matching patterns |
| `shell` | string | Shell for inline commands: `bash` (default) or `powershell` |

#### String substitutions in SKILL.md

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking skill; appended to content if `$ARGUMENTS` not present |
| `$ARGUMENTS[N]` | Specific argument by 0-based index (e.g., `$ARGUMENTS[0]` for first) |
| `$N` | Shorthand for `$ARGUMENTS[N]` (e.g., `$0`, `$1`) |
| `$name` | Named argument declared in `arguments` frontmatter (names map to positions in order) |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Directory containing skill's `SKILL.md` (for plugin skills, the skill subdirectory within plugin, not plugin root) |

#### Dynamic context injection

- **Inline form**: `` !`command` `` runs shell command before skill content sent to Claude; output replaces placeholder
- **Multi-line form**: ` ```! ` (backticks with exclamation) for multiple commands
- **Disable**: Set `disableSkillShellExecution: true` in settings (affects user, project, plugin, additional-directory skills; not bundled or managed skills)
- **Execution environment**: Runs in shell with command timeout; `$CLAUDE_SKILL_DIR` env var available
- **Extended thinking**: Include word "ultrathink" anywhere in skill content to enable extended thinking

#### Skill invocation

- **Automatic**: Claude invokes when description matches task (unless `disable-model-invocation: true`)
- **Manual**: User types `/skill-name` with optional arguments
- **With context fork**: If `context: fork` set, skill content becomes prompt for subagent (not main conversation)

#### Skill scope precedence

- **Enterprise** (highest): Managed settings
- **Personal**: `~/.claude/skills/`
- **Project**: `.claude/skills/`
- **Plugin** (lowest): `<plugin>/skills/`

**Note**: When same skill name in multiple locations, higher priority wins. Plugin skills use `plugin-name:skill-name` namespace (no conflicts).

#### Skill lifecycle in context compaction

- **Invocation**: Rendered `SKILL.md` content enters conversation as single message, stays for rest of session
- **Compaction**: When context fills, Claude Code re-attaches most recent invocation of each skill (first 5,000 tokens); re-attached skills share 25,000-token budget; oldest skills can be dropped if many invoked
- **Re-invocation after compaction**: Re-invoke skill after compaction to restore full content

#### Supporting files in skills

- **Templates**: Reference from `SKILL.md` (e.g., `[reference.md](reference.md)`)
- **Examples**: Show expected format
- **Scripts**: Executable utilities Claude can run
- **Keep SKILL.md under 500 lines**: Move detailed reference to separate files

**Sources:**
- https://docs.claude.com/en/docs/claude-code/skills (complete skills documentation, frontmatter, invocation, lifecycle, examples, patterns)

---

### Slash commands

**Note**: Custom commands have been merged into skills. A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way. Existing `.claude/commands/` files keep working.

- **Location (global)**: `~/.claude/commands/<name>.md`
- **Location (project)**: `.claude/commands/<name>.md`
- **Invocation**: `/<name>` in Claude Code
- **Format**: Markdown file with optional YAML frontmatter
- **Built-in commands**: `/help`, `/compact`, `/init`, `/review`, `/security-review`, `/memory`, `/config`, `/agents`, `/hooks`, `/mcp`, plus bundled skills like `/debug`, `/simplify`, `/batch`, `/loop`, `/claude-api`
- **Argument passing**: Text after command name accessible via `$ARGUMENTS` or positional `$0`, `$1`, etc.

**Sources:**
- https://docs.claude.com/en/docs/claude-code/skills (note: custom commands merged with skills)

---

### Plugins

#### Plugin manifest and structure

- **Manifest location**: `.claude-plugin/plugin.json` (required if component directories don't exist at standard locations)
- **Manifest fields**:
  - `name` (required): Unique identifier and skill namespace; becomes prefix for skills (e.g., `/plugin-name:skill-name`)
  - `description` (required): Shown in plugin manager
  - `version` (required): Semantic versioning
  - `author` (optional): Author metadata
  - `homepage`, `repository`, `license` (optional): Metadata fields

#### Plugin directory structure

- **`.claude-plugin/`**: Contains `plugin.json` only (optional if using default locations)
- **`skills/`**: Skills as `<name>/SKILL.md` directories
- **`commands/`**: Flat markdown files (legacy; `skills/` recommended for new)
- **`agents/`**: Custom agent definitions
- **`hooks/`**: Event handlers in `hooks.json`
- **`.mcp.json`**: MCP server configurations
- **`.lsp.json`**: LSP server configurations
- **`monitors/`**: Background monitors in `monitors.json`
- **`bin/`**: Executables added to Bash tool's PATH
- **`settings.json`**: Default settings applied when plugin enabled

**Important**: Do NOT put `commands/`, `agents/`, `skills/`, `hooks/` inside `.claude-plugin/` directory. Only `plugin.json` goes inside `.claude-plugin/`; all other directories must be at plugin root level.

#### Plugin skill naming

- **Global scope**: `/skill-name` (no namespace conflict risk)
- **Plugin scope**: `/plugin-name:skill-name` (namespaced to prevent conflicts)

#### Plugin security restrictions

- Plugin agents: Cannot use `hooks`, `mcpServers`, or `permissionMode` frontmatter fields (ignored when loading)
- If needed, copy agent file into `.claude/agents/` or `~/.claude/agents/`, or add rules to `permissions.allow`

#### Testing plugins locally

- **Command**: `claude --plugin-dir ./my-plugin`
- **Multiple plugins**: Specify flag multiple times: `--plugin-dir ./plugin-one --plugin-dir ./plugin-two`
- **Reload during session**: `/reload-plugins` picks up changes without restart
- **Precedence**: Local `--plugin-dir` plugin overrides installed marketplace plugin with same name (except force-enabled via managed settings)

#### Installing and distributing plugins

- **Installation**: Via `/plugin install` or marketplace
- **Marketplaces**: GitHub, npm registries, official Anthropic marketplace, custom
- **Force-enable**: Via managed settings `enabledPlugins` field
- **Default settings**: Plugin can define `settings.json` with `agent` field to set as main thread when enabled

#### Plugin MCP servers

- **Configuration**: `.mcp.json` at plugin root or inline in `plugin.json`
- **Lifecycle**: Auto-connect at session startup for enabled plugins; run `/reload-plugins` if enabling/disabling plugin mid-session
- **Environment variables**: Support `${CLAUDE_PLUGIN_ROOT}` (plugin installation directory) and `${CLAUDE_PLUGIN_DATA}` (persistent data directory surviving updates)

#### Plugin hooks

- **Scope**: Hooks in `hooks/hooks.json` apply when plugin enabled
- **Format**: Same as settings-based hooks
- **Merge**: Plugin hooks merge with user and project hooks
- **Top-level field**: Optional `description` field allowed

**Sources:**
- https://docs.claude.com/en/docs/claude-code/plugins (complete plugin creation, manifest, distribution, examples)

---

### Hooks

#### Hook lifecycle and events

**Hook events (complete list)**:

| Event | When it fires | Per-session or per-turn | Matcher support |
|-------|---------------|------------------------|-----------------|
| `SessionStart` | When session begins or resumes | Once per session | Matcher on how session started: `startup`, `resume`, `clear`, `compact` |
| `UserPromptSubmit` | Before Claude processes user prompt | Per-turn | No matcher |
| `UserPromptExpansion` | When user-typed command expands, before reaching Claude | Per-turn | Matcher on command name |
| `PreToolUse` | Before tool call executes | Per agentic loop | Matcher on tool name |
| `PermissionRequest` | When permission dialog appears | Per agentic loop | Matcher on tool name |
| `PermissionDenied` | Tool call denied by auto mode classifier | Per agentic loop | Matcher on tool name |
| `PostToolUse` | After tool call succeeds | Per agentic loop | Matcher on tool name |
| `PostToolUseFailure` | After tool call fails | Per agentic loop | Matcher on tool name |
| `Notification` | When Claude Code sends notification | Per agentic loop | Matcher on notification type: `permission_prompt`, `idle_prompt`, `auth_success`, `elicitation_dialog` |
| `SubagentStart` | When subagent is spawned | Per agentic loop | Matcher on agent type (e.g., `Bash`, `Explore`, `Plan`, custom agent names) |
| `SubagentStop` | When subagent finishes | Per agentic loop | Matcher on agent type |
| `TaskCreated` | When task being created via TaskCreate | Per agentic loop | No matcher |
| `TaskCompleted` | When task marked as completed | Per agentic loop | No matcher |
| `Stop` | When Claude finishes responding | Per-turn | No matcher |
| `StopFailure` | When turn ends due to API error | Per-turn | Matcher on error type: `rate_limit`, `authentication_failed`, `billing_error`, `invalid_request`, `server_error`, `max_output_tokens`, `unknown` |
| `TeammateIdle` | When agent team teammate about to go idle | Per agentic loop | No matcher |
| `InstructionsLoaded` | When CLAUDE.md or `.claude/rules/*.md` loads | Per session/lazy | Matcher on load reason: `session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact` |
| `ConfigChange` | When configuration file changes during session | Async | Matcher on config source: `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills` |
| `CwdChanged` | When working directory changes (e.g., `cd` command) | Async | No matcher |
| `FileChanged` | When watched file changes on disk | Async | Matcher on literal filenames to watch (e.g., `.envrc\|.env`) |
| `WorktreeCreate` | When worktree being created via `--worktree` or `isolation: "worktree"` | Per-session | No matcher |
| `WorktreeRemove` | When worktree being removed | Per-session | No matcher |
| `PreCompact` | Before context compaction | Per-session | Matcher on trigger: `manual`, `auto` |
| `PostCompact` | After context compaction completes | Per-session | Matcher on trigger: `manual`, `auto` |
| `Elicitation` | When MCP server requests user input during tool call | Per agentic loop | Matcher on MCP server name |
| `ElicitationResult` | After user responds to MCP elicitation, before response sent to server | Per agentic loop | Matcher on MCP server name |
| `SessionEnd` | When session terminates | Once per session | Matcher on why ended: `clear`, `resume`, `logout`, `prompt_input_exit`, `bypass_permissions_disabled`, `other` |

#### Hook configuration locations and scopes

| Location | Scope | Who manages | Shared with team |
|----------|-------|-------------|------------------|
| `~/.claude/settings.json` | All your projects | You | No |
| `.claude/settings.json` | Single project | You (committed to repo) | Yes |
| `.claude/settings.local.json` | Single project | You (gitignored) | No |
| Managed policy settings | Organization-wide | Administrator | Yes (enforced, cannot override) |
| Plugin `hooks/hooks.json` | When plugin enabled | Plugin author | Yes (bundled with plugin) |
| Skill/agent frontmatter | While component active | You | Yes (component is checked in) |

#### Hook handler types

**Command hooks** (`type: "command"`):
- **Input**: JSON via stdin
- **Output**: Exit code 0 (allow), 2 (block), other (non-blocking error); optionally JSON on stdout
- **Environment**: Runs in current directory with Claude Code's environment; `$CLAUDE_CODE_REMOTE` set to `"true"` in remote web, not set in local CLI
- **Timeout**: Default 600 seconds; configurable via `timeout` field
- **Fields**: `command` (required), `async` (boolean), `asyncRewake` (boolean), `shell` (bash or powershell)

**HTTP hooks** (`type: "http"`):
- **Request**: JSON POST to URL with `Content-Type: application/json`
- **Response**: 2xx with JSON body (same schema as command hook output), non-2xx (non-blocking error), connection failure/timeout (non-blocking)
- **Headers**: Static `headers` field; support environment variable interpolation with `$VAR_NAME` or `${VAR_NAME}` syntax (requires `allowedEnvVars` list)
- **Timeout**: Default 30 seconds; configurable
- **Fields**: `url` (required), `headers` (object), `allowedEnvVars` (list)

**Prompt hooks** (`type: "prompt"`):
- **Execution**: Send prompt to Claude model for single-turn evaluation
- **Output**: Yes/no decision as JSON
- **Fields**: `prompt` (required), `model` (optional, defaults to fast model)
- **Timeout**: Default 30 seconds

**Agent hooks** (`type: "agent"`):
- **Execution**: Spawn subagent with tool access (Read, Grep, Glob, Bash) to verify conditions
- **Output**: Decision as JSON
- **Fields**: `prompt` (required), `model` (optional)
- **Timeout**: Default 60 seconds
- **Status**: Experimental; may change

#### Common hook handler fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | `command`, `http`, `prompt`, or `agent` |
| `if` | No | Permission rule syntax to filter when hook runs (e.g., `Bash(git *)`, `Edit(*.ts)`). Only tool events: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`. If not matched, hook never runs |
| `timeout` | No | Seconds before canceling. Defaults: 600 (command), 30 (prompt), 60 (agent) |
| `statusMessage` | No | Custom spinner message while hook runs |
| `once` | No | If `true`, runs once per session then removed. Only honored in skill frontmatter |

#### Matcher patterns (how hooks filter)

- **`"*"`, `""`, or omitted**: Match all occurrences of event
- **Only letters, digits, `_`, `|`**: Exact string or `|`-separated list (e.g., `Bash`, `Edit|Write`)
- **Other characters (non-alphanumeric except `_` and `|`)**: JavaScript regular expression (e.g., `^Notebook`, `mcp__memory__.*`)

**Event-specific matcher fields**:

| Event | Matches against | Example values |
|-------|-----------------|-----------------|
| `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied` | Tool name | `Bash`, `Edit\|Write`, `mcp__.*` |
| `SessionStart` | How session started | `startup`, `resume`, `clear`, `compact` |
| `SessionEnd` | Why ended | `clear`, `resume`, `logout`, etc. |
| `Notification` | Notification type | `permission_prompt`, `idle_prompt`, `auth_success`, `elicitation_dialog` |
| `SubagentStart`, `SubagentStop` | Agent type | `Explore`, `Plan`, custom agent names |
| `PreCompact`, `PostCompact` | Trigger | `manual`, `auto` |
| `ConfigChange` | Config source | `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills` |
| `UserPromptExpansion` | Command name | Your skill or command names |
| `Elicitation`, `ElicitationResult` | MCP server name | Your configured MCP server names |
| Others no matcher support | — | Always fires |

**MCP tool matching**:
- **Format**: `mcp__<server>__<tool>` (e.g., `mcp__memory__create_entities`, `mcp__github__search_repositories`)
- **Wildcard matching**: `mcp__memory__.*` matches all tools from memory server; `mcp__.*__write.*` matches any tool starting with "write" from any server

#### Hook input and output

**Common input fields** (all hooks receive):

```json
{
  "session_id": "abc123",
  "transcript_path": "/home/user/.claude/projects/.../transcript.jsonl",
  "cwd": "/home/user/my-project",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse"
}
```

**Subagent-specific fields** (when inside subagent):

```json
{
  "agent_id": "unique-identifier-for-subagent",
  "agent_type": "Explore"
}
```

**Event-specific input fields** (example for `PreToolUse`):

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test"
  }
}
```

**JSON output schema** (exit code 0; ignored if exit 2):

```json
{
  "continue": false,
  "additionalContext": "string to add to context",
  "systemMessage": "string to add to system prompt",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "reason string",
    "retry": false
  }
}
```

#### Exit codes and behavior

**Exit code 0 (success)**:
- Parses stdout for JSON output
- JSON fields control behavior
- For `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`: stdout added as context Claude can see

**Exit code 2 (blocking error)**:
- Ignores stdout and any JSON in it
- Stderr text fed to Claude as error
- Effect depends on event:
  - `PreToolUse`: Blocks tool call
  - `PermissionRequest`: Denies permission
  - `UserPromptSubmit`: Blocks prompt processing, erases prompt
  - `UserPromptExpansion`: Blocks expansion
  - `Stop`, `SubagentStop`, `TeammateIdle`: Prevents stopping/idling
  - `TaskCreated`, `TaskCompleted`, `ConfigChange`: Rolls back action
  - `PreCompact`: Blocks compaction
  - `Elicitation`, `ElicitationResult`: Denies/blocks
  - `WorktreeCreate`: Creation fails
  - Others (`PostToolUse`, `Notification`, `SessionEnd`, etc.): Non-blocking (stderr shown to user only)

**Other exit codes (non-blocking error)**:
- Transcript shows `<hook name> hook error` with first line of stderr
- Full stderr in debug log
- Execution continues

#### Hook environment variables and path references

- **`$CLAUDE_PROJECT_DIR`**: Project root (wrapped in quotes for paths with spaces)
- **`${CLAUDE_PLUGIN_ROOT}`**: Plugin installation directory (for plugin hooks)
- **`${CLAUDE_PLUGIN_DATA}`**: Plugin persistent data directory (survives updates)

#### Hooks in skills and agents

- **Location**: Frontmatter `hooks:` object in skill or agent `.md` file
- **Format**: Same as settings-based hooks
- **Lifecycle**: Only run while component active; cleaned up when finishes
- **Supported events**: All hook events
- **Special case**: `Stop` in subagent frontmatter automatically converted to `SubagentStop` at runtime

#### Managed settings control of hooks

- **`allowManagedHooksOnly`** (boolean): Only managed hooks, SDK hooks, and force-enabled plugin hooks load. Blocks user, project, all other plugin hooks
- **`allowedHttpHookUrls`** (array): Allowlist of URL patterns HTTP hooks may target. Supports `*` wildcard. When set, non-matching hooks blocked. Undefined = no restriction, empty = block all. Arrays merge across sources
- **`httpHookAllowedEnvVars`** (array): Allowlist of env var names hooks may interpolate into headers. When set, each hook's effective allowlist is intersection with this. Undefined = no restriction. Arrays merge

#### The `/hooks` menu

- **Access**: Type `/hooks` in Claude Code
- **View**: Read-only browser showing all configured hooks, event counts, matcher details
- **Type labels**: `[command]`, `[http]`, `[prompt]`, `[agent]`
- **Sources**: User, Project, Local, Plugin, Session, Built-in

#### Disabling or removing hooks

- **Remove**: Delete entry from settings JSON
- **Disable all**: Set `"disableAllHooks": true` (respects hierarchy; managed setting can disable all, but user setting cannot disable managed hooks)

**Sources:**
- https://docs.claude.com/en/docs/claude-code/hooks (complete hook reference, all events, input/output schema, exit codes, examples)

---

### MCP servers

#### Configuration and installation

- **User scope configuration**: `~/.claude.json` (per-project entry)
- **Project scope configuration**: `.mcp.json` at project root (checked into repo, shared)
- **Plugin scope**: Plugin `.mcp.json` at plugin root
- **Scope precedence**: Local (project) > Project (`.mcp.json`) > User > Plugin > Claude.ai connectors

#### Installation via CLI

```bash
# HTTP
claude mcp add --transport http <name> <url>

# SSE (deprecated)
claude mcp add --transport sse <name> <url> [--header "key: value"]

# Stdio
claude mcp add --transport stdio <name> -- <command> [args...]
```

**Option ordering**: All options (`--transport`, `--env`, `--scope`, `--header`) must come BEFORE server name; `--` separates name from command and args

#### Configuration format (.mcp.json)

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http|sse|stdio",
      "url": "https://...",        // http/sse
      "command": "...",             // stdio
      "args": ["arg1", "arg2"],    // stdio
      "env": {
        "KEY": "value"
      },
      "headers": {
        "Authorization": "Bearer token"
      },
      "oauth": {
        "clientId": "...",
        "clientSecret": "...",
        "scope": "...",
        "authServerMetadataUrl": "...",
        "callbackPort": 8080
      },
      "headersHelper": "/path/to/script.sh",
      "timeout": 30000
    }
  }
}
```

#### Environment variable expansion in .mcp.json

- **Syntax**: `${VAR}` or `${VAR:-default}` (expands to default if VAR unset)
- **Locations**: `command`, `args`, `env`, `url`, `headers`
- **Unset required vars**: Config parse fails with error

#### Authentication methods

**Automatic OAuth** (for compatible servers):
- No special config needed; Claude Code detects 401 and initiates flow
- Uses Dynamic Client Registration (RFC 7591) if supported
- Tokens stored securely and auto-refreshed

**Pre-configured OAuth credentials**:
```json
{
  "oauth": {
    "clientId": "your-id",
    "clientSecret": "your-secret",
    "scope": "requested scopes",
    "callbackPort": 8080
  }
}
```

**Fixed OAuth callback port**:
```bash
claude mcp add --transport http --callback-port 8080 my-server https://mcp.example.com/mcp
```

**Custom OAuth metadata discovery**:
```json
{
  "oauth": {
    "authServerMetadataUrl": "https://auth.example.com/.well-known/openid-configuration"
  }
}
```

**Restrict OAuth scopes** (pin to approved subset):
```json
{
  "oauth": {
    "scopes": "channels:read chat:write search:read"
  }
}
```

**Dynamic headers** (custom auth schemes, short-lived tokens, Kerberos, internal SSO):
```json
{
  "headersHelper": "/opt/bin/get-mcp-auth-headers.sh"
}
```
Script outputs JSON key-value pairs to stdout; runs at connection time with env vars `CLAUDE_CODE_MCP_SERVER_NAME`, `CLAUDE_CODE_MCP_SERVER_URL`

#### Per-agent MCP server selection

- **Frontmatter field**: `mcpServers:`
- **Format**: Array of either string references or inline definitions
- **Inline definitions**: `server-name: { type: "http"|"sse"|"stdio", ... }`
- **String references**: Pre-configured server name (reuses existing connection)

```yaml
---
name: browser-tester
mcpServers:
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
  - github
---
```

#### MCP server management commands

```bash
claude mcp list                    # List all configured servers
claude mcp get <name>              # Get details for specific server
claude mcp remove <name>           # Remove server
claude mcp add-json <name> '...'   # Add from JSON config
claude mcp auth <server>           # Authenticate with OAuth
claude mcp logout <server>         # Remove stored credentials
claude mcp reset-project-choices   # Reset project-scoped server approvals
claude mcp add-from-claude-desktop # Import from Claude Desktop config (macOS/WSL only)
```

#### In-session MCP management

- **Command**: `/mcp` in Claude Code
- **Actions**: View status, authenticate, manage servers

#### Dynamic tool updates

- **Feature**: MCP servers can send `list_changed` notifications to update tools/prompts/resources dynamically
- **Behavior**: Claude Code auto-refreshes available capabilities from server (no reconnect needed)

#### Automatic reconnection

- **HTTP/SSE**: Up to 5 attempts with exponential backoff (start 1s, double each time)
- **Stdio**: Local process, not reconnected automatically
- **Failed**: Server marked as failed; retry manually from `/mcp`

#### MCP output limits and warnings

- **Warning threshold**: 10,000 tokens
- **Default maximum**: 25,000 tokens
- **Configurable**: `MAX_MCP_OUTPUT_TOKENS` env var (e.g., `MAX_MCP_OUTPUT_TOKENS=50000 claude`)
- **Per-tool override**: Tool can declare `anthropic/maxResultSizeChars` in `tools/list` response (up to 500,000 chars for text; images still subject to token limit)
- **Tool search deferred loading**: Only tool names load at startup; Claude discovers tool definitions on demand (reduces context usage for large tool sets)

#### MCP resources and prompts

- **Resources**: Reference via `@server:protocol://resource/path` in prompts
- **Prompts**: Available as commands `/mcp__servername__promptname [arguments]`

#### Plugin MCP servers

- **Configuration**: `.mcp.json` at plugin root or inline in `plugin.json`
- **Lifecycle**: Auto-connect when plugin enabled; run `/reload-plugins` if enabling/disabling mid-session
- **Example**.mcp.json:
```json
{
  "mcpServers": {
    "database-tools": {
      "type": "stdio",
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
      "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
      "env": {
        "DB_URL": "${DB_URL}"
      }
    }
  }
}
```

#### Managed MCP configuration

**Option 1: Exclusive control** (`managed-mcp.json`):
- **Location**: System directory (macOS `/Library/Application Support/ClaudeCode/`, Linux `/etc/claude-code/`, Windows `C:\Program Files\ClaudeCode\`)
- **Effect**: Only servers in this file available; users cannot add/modify
- **Format**: Same as `.mcp.json`

**Option 2: Policy-based control** (allowlists/denylists in managed settings):
- **Fields**: `allowedMcpServers`, `deniedMcpServers`
- **Restriction types** (use one per entry):
  - `serverName`: "github"
  - `serverCommand`: ["npx", "-y", "@modelcontextprotocol/server-everything"]
  - `serverUrl`: "https://mcp.company.com/*" (wildcard support)
- **Precedence**: Denylist takes precedence over allowlist
- **`allowManagedMcpServersOnly`**: If true, only allowlist respected; users can add servers but only allowlist applies

#### Claude.ai connector servers

- **Auto-available**: If logged in with Claude.ai account, MCP servers added at claude.ai/customize/connectors automatically available in Claude Code
- **Disable**: Set `ENABLE_CLAUDEAI_MCP_SERVERS=false` env var

#### Use Claude Code as MCP server

```bash
claude mcp serve
```

Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "claude-code": {
      "type": "stdio",
      "command": "/full/path/to/claude",
      "args": ["mcp", "serve"]
    }
  }
}
```

**Sources:**
- https://docs.claude.com/en/docs/claude-code/mcp (complete MCP reference, installation, auth, plugins, examples)

---

### Settings.json

#### Top-level keys and structure

**User settings location**: `~/.claude/settings.json` (all projects)
**Project settings location**: `.claude/settings.json` (checked in) and `.claude/settings.local.json` (gitignored)
**Schema**: Available at `https://json.schemastore.org/claude-code-settings.json`

#### Complete settings table

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `$schema` | string | — | Point to schema: `https://json.schemastore.org/claude-code-settings.json` |
| `agent` | string | — | Run main thread as named subagent (applies subagent's system prompt, tools, model) |
| `allowedChannelPlugins` | array | Anthropic allowlist | (Managed only) Allowlist of channel plugins that may push messages; `[{marketplace, plugin}]` |
| `allowedHttpHookUrls` | array | No restriction | Allowlist of URL patterns HTTP hooks may target; supports `*` wildcard |
| `allowedMcpServers` | array | — | (Managed) Allowlist of MCP servers users can configure; `[{serverName}]` or `[{serverCommand}]` or `[{serverUrl}]` |
| `allowManagedHooksOnly` | boolean | false | (Managed) Block user/project hooks; only managed/SDK/force-enabled plugin hooks load |
| `allowManagedMcpServersOnly` | boolean | false | (Managed) Only allowlist applied; users can add but only allowlist takes effect |
| `allowManagedPermissionRulesOnly` | boolean | false | (Managed) Prevent user/project permission rules; only managed rules apply |
| `alwaysThinkingEnabled` | boolean | false | Enable extended thinking by default |
| `apiKeyHelper` | string | — | Shell script to generate auth value (sent as `X-Api-Key` and `Authorization: Bearer` headers) |
| `attribution` | object | `{commit: "🤖 Generated with Claude Code", pr: ""}` | Customize git commit/PR attribution: `{commit: "text", pr: "text"}` |
| `autoMemoryEnabled` | boolean | true | Enable auto memory (persist learnings across sessions) |
| `autoMemoryDirectory` | string | `~/.claude/projects/<project>/memory/` | Custom directory for auto memory (accepts `~/`-expanded paths; not in project settings) |
| `autoMode` | object | — | Customize auto mode classifier blocking/allowing: `{environment: [], allow: [], soft_deny: []}` (prose rules) |
| `autoUpdatesChannel` | string | `latest` | Release channel: `stable` (week-old, skip regressions) or `latest` (most recent) |
| `availableModels` | array | All | Restrict which models users can select; list of model aliases |
| `awaySummaryEnabled` | boolean | true | Show one-line recap when returning after idle time |
| `awsAuthRefresh` | string | — | Custom script modifying `.aws` directory (advanced credential config for Bedrock) |
| `awsCredentialExport` | string | — | Custom script outputting JSON with AWS credentials (advanced Bedrock config) |
| `blockedMarketplaces` | array | — | (Managed) Blocklist of marketplace sources (blocks before download): `[{source, repo}]` |
| `channelsEnabled` | boolean | false | (Managed) Allow channels for Team/Enterprise users |
| `cleanupPeriodDays` | integer | 30 (min 1) | Session files older than this deleted at startup; also controls orphaned worktree cleanup |
| `claudeMdExcludes` | array | — | Glob patterns to skip specific CLAUDE.md files (in large monorepos) |
| `companyAnnouncements` | array | — | Announcements to display at startup (cycled randomly) |
| `defaultShell` | string | `bash` | Default shell for `!` commands: `bash` or `powershell` (powershell requires `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`) |
| `deniedMcpServers` | array | — | (Managed) Denylist of MCP servers (takes precedence over allowlist): `[{serverName}]` |
| `disableAllHooks` | boolean | false | Disable all hooks and custom status line |
| `disableAutoMode` | string | — | Set to `"disable"` to prevent auto mode activation; removes from Shift+Tab cycle |
| `disabledMcpjsonServers` | array | — | Specific MCP servers from `.mcp.json` files to reject |
| `disableDeepLinkRegistration` | string | — | Set to `"disable"` to prevent `claude-cli://` protocol handler registration |
| `disableSkillShellExecution` | boolean | false | (Managed) Disable inline shell execution (`` !`...` ``) in skills/commands from user/project/plugin/additional-dir sources |
| `effortLevel` | string | — | Persist effort level: `low`, `medium`, `high`, `xhigh` |
| `enableAllProjectMcpServers` | boolean | false | Auto-approve all MCP servers from `.mcp.json` |
| `enabledMcpjsonServers` | array | — | Specific MCP servers from `.mcp.json` to approve |
| `env` | object | `{}` | Environment variables applied to every session |
| `fastModePerSessionOptIn` | boolean | false | Fast mode requires per-session opt-in; doesn't persist |
| `feedbackSurveyRate` | number | Varies | Probability (0–1) session quality survey appears |
| `fileSuggestion` | object | — | Custom script for `@` file autocomplete: `{type: "command", command: "..."}` |
| `forceLoginMethod` | string | — | Restrict login: `claudeai` (Claude.ai accounts only) or `console` (API usage billing) |
| `forceLoginOrgUUID` | string or array | — | Require login to specific organization UUID(s) |
| `forceRemoteSettingsRefresh` | boolean | false | (Managed) Block startup until remote settings freshly fetched |
| `hooks` | object | `{}` | Hook configuration (event → matcher → handler array) |
| `httpHookAllowedEnvVars` | array | — | Allowlist of env var names hooks may interpolate into headers |
| `includeCoAuthoredBy` | string | **Deprecated** | Use `attribution` instead |
| `includeGitInstructions` | boolean | true | Include built-in git workflow instructions in system prompt |
| `language` | string | — | Preferred response language (e.g., `japanese`, `spanish`, `french`); also sets voice dictation language |
| `minimumVersion` | string | — | Floor version; prevents downgrade below this |
| `model` | string | — | Override default model |
| `modelOverrides` | object | `{}` | Map Anthropic model IDs to provider-specific IDs (e.g., Bedrock ARNs): `{claude-opus-4-6: "arn:aws:..."}` |
| `otelHeadersHelper` | string | — | Script generating dynamic OpenTelemetry headers (runs at startup/periodically) |
| `outputStyle` | string | — | Configure output style (adjusts system prompt) |
| `permissions` | object | `{}` | Permission rules: `{allow: [], ask: [], deny: []}` (tool-specific rules) |
| `plansDirectory` | string | `~/.claude/plans` | Where plan files stored (relative to project root) |
| `pluginTrustMessage` | string | — | (Managed) Custom message appended to plugin trust warning |
| `prefersReducedMotion` | boolean | false | Disable UI animations for accessibility |
| `respectGitignore` | boolean | true | `@` file picker respects `.gitignore` patterns |
| `showClearContextOnPlanAccept` | boolean | false | Show "clear context" option on plan accept screen |
| `showThinkingSummaries` | boolean | false | Show extended thinking summaries (non-interactive default is true) |
| `skipWebFetchPreflight` | boolean | false | Skip WebFetch domain safety check (for Bedrock/Vertex/Foundry with restrictive egress) |
| `spinnerTipsEnabled` | boolean | true | Show tips in spinner while Claude works |
| `strictKnownMarketplaces` | array | — | (Managed) Restrict plugin marketplace additions to allowlist |

#### Permissions structure

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run lint)",
      "Bash(npm run test *)",
      "Read(~/.zshrc)"
    ],
    "ask": [...],
    "deny": [
      "Bash(curl *)",
      "Read(./.env)",
      "Read(./secrets/**)"
    ]
  }
}
```

**Syntax**:
- Tool names: `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `WebFetch`, `Skill(<name>)`, `Agent(<name>)`, `MCP tools`
- Arguments: `Bash(git *)` (subcommand matching), `Edit(*.ts)` (file patterns)
- Wildcards: `*` (zero or more), `?` (one character)
- `Skill(name)` exact match or `Skill(name *)` prefix match
- `Agent(name)` restrict subagent spawning; `Agent(worker, researcher)` allowlist

#### Auto mode classifier configuration

```json
{
  "autoMode": {
    "environment": ["Trusted repo: github.example.com/acme"],
    "allow": ["npm test", "git diff"],
    "soft_deny": ["curl https://external-api.com"]
  }
}
```

#### Scope precedence

1. **Managed settings** (highest; cannot be overridden): Server-delivered, MDM/OS plist, file-based in system directories
2. **Command line arguments**: `--model`, `--permission-mode`, etc. (per session)
3. **Local settings**: `.claude/settings.local.json` (overrides project, user)
4. **Project settings**: `.claude/settings.json` (checked in, shared)
5. **User settings**: `~/.claude/settings.json` (personal)
6. **Plugin defaults** (lowest): Plugin `settings.json`

**Note**: Arrays merge across scopes; later values override earlier for scalars; objects deep-merged.

**Sources:**
- https://docs.claude.com/en/docs/claude-code/settings (complete settings reference, all keys, scopes, examples)

---

### Provider support

#### Native providers

| Provider | API Endpoint | Model ID Format | Examples | Setup Required |
|----------|--------------|-----------------|----------|-----------------|
| **Anthropic** | api.anthropic.com | Model alias or full ID | `sonnet`, `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5` | Claude subscription or Console API key |
| **Amazon Bedrock** | bedrock-runtime.*.amazonaws.com | ARN format | `arn:aws:bedrock:us-east-1:123456789:inference-profile/anthropic.claude-3-5-sonnet-20241022-v2:0` | AWS account with model access; IAM credentials; optional VPC endpoint; optional profile-based auth |
| **Google Vertex AI** | vertexai.googleapis.com | Model with location suffix | `claude-3-5-sonnet@...` | GCP project with Vertex API enabled; service account with permissions |
| **Microsoft Foundry** | Azure resource URL | Model deployment ID | Varies by deployment | Azure subscription; Foundry resource; model deployments provisioned |
| **GitHub Copilot** (third-party) | github-copilot API | Provider alias | `github-copilot/claude-code` | GitHub token from `/connect` |

#### Model ID formats by provider

**Anthropic** (direct API):
- Aliases: `sonnet`, `opus`, `haiku` (map to latest versions)
- Full IDs: `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5`, etc.
- Usage: `--model claude-sonnet-4-6` or settings `"model": "sonnet"`

**Bedrock** (AWS):
- ARN format: `arn:aws:bedrock:<region>:<account-id>:inference-profile/<anthropic-model-id>`
- Example: `arn:aws:bedrock:us-east-1:123456789:inference-profile/anthropic.claude-3-5-sonnet-20241022-v2:0`
- Config: Set in `settings.json` `modelOverrides` to map Anthropic ID to ARN

**Vertex AI** (Google):
- Format: `claude-3-5-sonnet@<version>` or similar (location inferred from GCP project)
- Example: `claude-3-5-sonnet@20250514` (version date)
- Setup guide required from docs

**Foundry** (Microsoft Azure):
- Format: Deployment-specific; depends on how models provisioned
- Setup guide required from docs

**GitHub Copilot**:
- Format: `github-copilot/claude-code` (passed as model provider/alias)
- Auth: Via `/connect` or `GITHUB_TOKEN` env var

#### Model alias resolution

- `sonnet` → Latest Claude Sonnet (currently 4.6 or later)
- `opus` → Latest Claude Opus (currently 4.7 or later)
- `haiku` → Latest Claude Haiku (currently 4.5 or later)
- `inherit` → Use parent/session model

#### Per-agent model override

- **Subagent frontmatter**: `model: sonnet` or `model: claude-opus-4-7` or `model: inherit`
- **Skill frontmatter**: `model: haiku`
- **Per-invocation** (Agent tool): Claude can pass `model` parameter
- **Environment variable**: `CLAUDE_CODE_SUBAGENT_MODEL` overrides subagent definition's `model` field

#### Provider configuration

**Bedrock advanced options** (in `settings.json`):
```json
{
  "provider": {
    "amazon-bedrock": {
      "options": {
        "region": "us-east-1",
        "profile": "my-aws-profile",
        "endpoint": "https://bedrock-runtime.vpce-xxxxx.amazonaws.com"
      }
    }
  }
}
```

**Auth precedence**:
1. Bearer token (AWS_BEARER_TOKEN_BEDROCK or `/connect`)
2. Profile-based auth (~/.aws/credentials)
3. Environment variables
4. Default credentials chain

**Sources:**
- https://docs.claude.com/en/docs/claude-code/overview (providers section)
- https://docs.claude.com/en/docs/claude-code/settings (provider options, model configuration)

---

## OpenCode

### Installation paths

- **Global config directory**: `~/.config/opencode/`
- **Local project directory**: `.opencode/`
- **Global config file**: `~/.config/opencode/opencode.json` or `opencode.jsonc`
- **Project config file**: `opencode.json` or `opencode.jsonc` at project root
- **Custom config path**: Via `OPENCODE_CONFIG` env var
- **Custom config directory**: Via `OPENCODE_CONFIG_DIR` env var
- **Inline config**: `OPENCODE_CONFIG_CONTENT` env var (runtime overrides)
- **TUI config (global)**: `~/.config/opencode/tui.json` or `tui.jsonc`
- **TUI config (project)**: `tui.json` or `tui.jsonc` at project root
- **Managed settings (macOS)**: `/Library/Application Support/opencode/opencode.json` or `.opencode/` drop-in directory
- **Managed settings (Linux)**: `/etc/opencode/opencode.json` or `opencode.d/` directory
- **Managed settings (Windows)**: `%ProgramData%\opencode\opencode.json`
- **macOS MDM managed preferences**: `ai.opencode.managed` plist domain via `.mobileconfig`
- **Rules file (project)**: `AGENTS.md` (preferred) or `CLAUDE.md` (fallback for Claude Code compatibility)
- **Rules file (global)**: `~/.config/opencode/AGENTS.md`
- **Rules file (Claude Code fallback)**: `~/.claude/CLAUDE.md` (if `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1` not set)

**Sources:**
- https://opencode.ai/docs/config (installation paths, config locations, precedence)

---

### Agents

#### Primary agents (built-in)

| Name | Model | Tools | Purpose | Shortcut |
|------|-------|-------|---------|----------|
| **Build** | Session model | All enabled | Default; full development work | **Tab** to cycle |
| **Plan** | Session model | Read-only (ask mode for edits/bash) | Planning and analysis without changes | **Tab** to cycle |

#### Subagents (built-in)

| Name | Model | Tools | Purpose | Invocation |
|------|-------|-------|---------|------------|
| **General** | Session model | All | Complex research, multi-step operations | `@general` mention or automatic delegation |
| **Explore** | Session model | Read-only | Fast codebase exploration | `@explore` mention or automatic delegation |

#### Hidden system agents

| Name | Model | Purpose |
|------|-------|---------|
| **Compaction** | Session model | Auto-compacts long context into smaller summary |
| **Title** | Session model | Generates short session titles |
| **Summary** | Session model | Creates session summaries |

#### Custom agent configuration

**Location** (priority order):
1. Managed settings in system directory
2. `opencode.json` `agent` field
3. `~/.config/opencode/agents/` (global)
4. `.opencode/agents/` (project)

**Via JSON** (`opencode.json`):
```json
{
  "agent": {
    "code-reviewer": {
      "description": "Reviews code for best practices",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-20250514",
      "prompt": "You are a code reviewer...",
      "temperature": 0.1,
      "tools": {
        "write": false,
        "edit": false
      }
    }
  }
}
```

**Via Markdown** (`.opencode/agents/review.md` or `~/.config/opencode/agents/review.md`):
```yaml
---
description: Reviews code for quality and best practices
mode: subagent
model: anthropic/claude-sonnet-4-20250514
temperature: 0.1
permission:
  edit: deny
  bash: deny
---

You are a code reviewer. Focus on security, performance, and maintainability.
```

#### Agent frontmatter fields

| Field | Required | Type | Default | Description |
|-------|----------|------|---------|-------------|
| `description` | **Yes** | string | — | When to use this agent; determines automatic delegation |
| `mode` | No | string | `all` | `primary`, `subagent`, or `all` |
| `temperature` | No | number | Model default | 0.0–1.0 randomness control |
| `model` | No | string | Inherit session | Model ID (e.g., `anthropic/claude-sonnet-4-20250514`) |
| `prompt` | No | string | — | Custom system prompt (file ref: `{file:./path.txt}`) |
| `steps` | No | integer | Unlimited | Max agentic iterations (cost control) |
| `disable` | No | boolean | false | Disable agent |
| `permission` | No | object | `{}` | Tool permissions: `{edit: "ask\|allow\|deny", bash: {...}, webfetch: "ask\|allow\|deny"}` |
| `color` | No | string | — | Display color: `primary`, `secondary`, `accent`, `success`, `warning`, `error`, `info`, or hex (#FF5733) |
| `top_p` | No | number | — | Alternative to temperature (0.0–1.0) |
| `hidden` | No | boolean | false | Hide subagent from `@` autocomplete (only applies to `mode: subagent`) |
| `task` (permission field) | No | object | — | Restrict which subagents this agent can invoke via Task tool: `{agent-name: "allow\|ask\|deny", "*": "deny"}` |
| `default_agent` | — | string | — | Global setting: default primary agent when none specified |
| **Additional provider fields** | No | various | — | Pass through to provider (e.g., OpenAI's `reasoningEffort: "high"`) |

#### Permission configuration (agent-level)

```json
{
  "agent": {
    "build": {
      "permission": {
        "edit": "ask",
        "bash": {
          "*": "ask",
          "git status *": "allow",
          "rm -rf *": "deny"
        },
        "webfetch": "allow"
      }
    }
  }
}
```

**Permission values**: `ask` (prompt for approval), `allow` (auto-approve), `deny` (block tool)
**Bash subcommand patterns**: Glob patterns (`git *`), specific commands (`git status`), exact match

#### Global permission configuration

```json
{
  "permission": {
    "edit": "ask",
    "bash": {
      "*": "ask",
      "npm test": "allow"
    },
    "webfetch": "deny"
  }
}
```

**Override per agent**: Agent-specific `permission` field overrides global

#### How agents differ from Claude Code

- **No Memory concept**: OpenCode agents don't have built-in auto-memory like Claude Code; rules are static (AGENTS.md)
- **Permission model**: Tool-level `permission: {edit, bash, webfetch}` instead of Claude Code's agent-level `permissionMode`
- **No frontmatter-level hooks**: OpenCode agents don't support hook definitions in frontmatter (unlike Claude Code)
- **No MCP scoping**: Cannot assign MCP servers to agents via frontmatter (global only)

#### Setting default agent

```json
{
  "default_agent": "plan"
}
```

**Must be a primary agent** (not subagent); defaults to `build` if not specified or if agent doesn't exist

#### Invocation

- **Primary agents**: **Tab** key cycles through during session
- **Subagents**: `@agent-name` mention in message, or automatic delegation by OpenCode
- **Session-wide**: Set `default_agent` or pass `--agent` flag to `opencode run`

**Sources:**
- https://opencode.ai/docs/agents (complete agent configuration, built-in agents, examples, options)

---

### Rules

#### Rule files (AGENTS.md)

**Locations** (precedence):
1. Local `AGENTS.md` (walk up from current directory)
2. Global `~/.config/opencode/AGENTS.md`
3. Claude Code fallback `CLAUDE.md` (if `OPENCODE_DISABLE_CLAUDE_CODE=1` not set)

**Format**: Plain markdown (no required frontmatter)
**Activation**: Loaded at session start; always included in context
**Scope**: Project or global (user)

#### Precedence order for rule loading

1. **Local rules** by traversing up (`AGENTS.md`, then `CLAUDE.md`)
2. **Global rule** at `~/.config/opencode/AGENTS.md`
3. **Claude Code fallback** at `~/.claude/CLAUDE.md`

#### Custom instructions via opencode.json

```json
{
  "instructions": [
    "CONTRIBUTING.md",
    "docs/guidelines.md",
    ".cursor/rules/*.md",
    "https://raw.githubusercontent.com/org/rules/main/style.md"
  ]
}
```

**Features**:
- File paths (relative or absolute, glob patterns)
- Remote URLs (5-second timeout)
- All instruction files combined with `AGENTS.md` files

#### Claude Code compatibility

- **Project level**: OpenCode reads `CLAUDE.md` if no `AGENTS.md` exists
- **Global level**: OpenCode reads `~/.claude/CLAUDE.md` if no `~/.config/opencode/AGENTS.md` exists
- **Disable fallback**: Set env var `OPENCODE_DISABLE_CLAUDE_CODE=1` (disables all `.claude` support) or `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1` (only global `CLAUDE.md`)

#### Manually reference external files in AGENTS.md

```markdown
# Project Rules

Read this file for general guidance: @rules/general-guidelines.md

When you encounter a file reference (e.g., @docs/typescript-guidelines.md), use your Read tool to load it.
```

**Note**: OpenCode does NOT automatically expand `@file` references; you must instruct the agent to load them on-demand (unlike Claude Code's import system)

#### Key differences from Claude Code

- **No auto-memory**: AGENTS.md rules are static; no persistent memory directory updates
- **No `## Memory` section support**: OpenCode ignores memory sections; they should be removed when migrating from Claude Code
- **Plain markdown only**: No frontmatter in AGENTS.md itself (unlike Claude Code's CLAUDE.md which can have frontmatter)

**Sources:**
- https://opencode.ai/docs/rules (rules configuration, locations, precedence, Claude Code compatibility)

---

### Skills

- **Full support**: OpenCode supports Agent Skills standard (same as Claude Code)
- **Location (global)**: `~/.config/opencode/skills/<skill-name>/SKILL.md`
- **Location (project)**: `.opencode/skills/<skill-name>/SKILL.md`
- **Format**: YAML frontmatter + markdown body (identical to Claude Code)
- **Frontmatter fields**: Same as Claude Code (all optional except `description` recommended)
- **Invocation**: `/skill-name` from `@` autocomplete or via `opencode.json` `command` field

**Sources:**
- https://opencode.ai/docs/skills (full Agent Skills support)

---

### Commands

#### Custom command configuration

**Via JSON** (`opencode.json`):
```json
{
  "command": {
    "test": {
      "template": "Run the full test suite with coverage...",
      "description": "Run tests with coverage",
      "agent": "build",
      "model": "anthropic/claude-3-5-sonnet-20241022"
    }
  }
}
```

**Via Markdown** (`.opencode/commands/test.md` or `~/.config/opencode/commands/test.md`):
```yaml
---
description: Run tests with coverage
agent: build
model: anthropic/claude-3-5-sonnet-20241022
---

Run the full test suite with coverage report and show any failures.
Focus on the failing tests and suggest fixes.
```

#### Command frontmatter fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | **Yes** | What command does (shown in TUI) |
| `template` | string | **Yes** (JSON) or markdown body | Prompt sent to LLM |
| `agent` | string | No | Agent to use for command |
| `subtask` | boolean | No | Force subagent invocation (even if agent is primary) |
| `model` | string | No | Model override for command |

#### Command invocation

- **Syntax**: `/<command-name>` in TUI
- **With arguments**: `/command-name arg1 arg2`
- **Placeholders**: `$ARGUMENTS` (all args), `$0`, `$1` (positional)
- **Shell injection**: `!`command`` or ` ```! ` for dynamic context
- **File references**: `@filename` syntax
- **Overrides**: Custom commands can override built-in commands (`/init`, `/undo`, `/redo`, `/share`, `/help`)

**Sources:**
- https://opencode.ai/docs/commands (command configuration and invocation)

---

### MCP servers

#### Configuration via opencode.json

```json
{
  "mcp": {
    "my-server": {
      "type": "local|remote",
      "enabled": true,
      "timeout": 5000,
      "environment": {...}
    }
  }
}
```

#### Local MCP servers (stdio)

```json
{
  "mcp": {
    "my-mcp": {
      "type": "local",
      "command": ["npx", "-y", "my-mcp-command"],
      "environment": {
        "MY_ENV_VAR": "value"
      },
      "timeout": 5000
    }
  }
}
```

#### Remote MCP servers (HTTP)

```json
{
  "mcp": {
    "sentry": {
      "type": "remote",
      "url": "https://mcp.sentry.dev/mcp",
      "headers": {
        "Authorization": "Bearer token"
      },
      "oauth": {
        "clientId": "...",
        "clientSecret": "...",
        "scope": "..."
      },
      "timeout": 5000
    }
  }
}
```

#### OAuth authentication

**Automatic**: No config needed; OpenCode detects 401 and initiates Dynamic Client Registration flow
**Pre-configured**: Set `clientId`, `clientSecret`, `scope` in `oauth` object
**Disable**: Set `oauth: false` to disable auto-detection (for API key-based servers)

#### OAuth management commands

```bash
opencode mcp auth <server-name>              # Authenticate with server
opencode mcp logout <server-name>            # Remove credentials
opencode mcp auth list                       # List auth status
opencode mcp debug <server-name>             # Diagnose connection/OAuth
```

#### MCP server management

**Global scope** (all projects):
```json
{
  "mcp": {
    "github": {
      "type": "remote",
      "url": "https://api.githubcopilot.com/mcp/"
    }
  },
  "tools": {
    "github_*": false  // Disable via tools glob pattern
  }
}
```

**Per-agent scope** (restrict to specific agents):
```json
{
  "mcp": {
    "jira": {
      "type": "remote",
      "url": "https://jira.example.com/mcp"
    }
  },
  "tools": {
    "jira_*": false  // Disable globally
  },
  "agent": {
    "issue-reviewer": {
      "tools": {
        "jira_*": true  // Enable only for this agent
      }
    }
  }
}
```

#### Glob patterns for MCP tools

- **Syntax**: Simple regex globbing (`*` = zero or more chars, `?` = one char)
- **Example**: `mymcp_*` matches all tools from server named `mymcp`
- **Tool naming**: OpenCode registers MCP tools as `<server-name>_<tool-name>`

#### Supported MCP server types

| Type | Transport | Use case |
|------|-----------|----------|
| `local` | stdio | Local executable, bundled scripts |
| `remote` | HTTP | Cloud services, remote APIs |
| UNVERIFIED | SSE | Server-Sent Events (if supported) |

#### Remote config override (organization defaults)

```json
{
  "mcp": {
    "jira": {
      "type": "remote",
      "url": "https://jira.example.com/mcp",
      "enabled": true  // Override org default (was disabled)
    }
  }
}
```

**Precedence**: Local config merges with remote; local values override

**Sources:**
- https://opencode.ai/docs/mcp-servers (MCP server configuration, OAuth, examples, glob patterns)

---

### Provider support

#### Available providers

| Provider | Format | Example |
|----------|--------|---------|
| Anthropic | `provider/model-id` | `anthropic/claude-sonnet-4-20250514` |
| OpenAI | `provider/model-id` | `openai/gpt-4o` |
| Gemini | `provider/model-id` | `google/gemini-2.0-flash` |
| Amazon Bedrock | `provider/model-id` | AWS-specific format |
| Azure | `provider/model-id` | Azure deployment format |
| Custom local | `provider/model-id` | Custom provider with local model |

#### Model configuration

**Global default**:
```json
{
  "model": "anthropic/claude-sonnet-4-20250514",
  "small_model": "anthropic/claude-haiku-4-5"
}
```

**Provider options**:
```json
{
  "provider": {
    "anthropic": {
      "options": {
        "timeout": 600000,
        "chunkTimeout": 30000,
        "setCacheKey": true
      }
    },
    "amazon-bedrock": {
      "options": {
        "region": "us-east-1",
        "profile": "my-profile",
        "endpoint": "https://bedrock-runtime.vpce-xxxxx.amazonaws.com"
      }
    }
  }
}
```

#### Per-agent model override

```json
{
  "agent": {
    "plan": {
      "model": "anthropic/claude-haiku-4-5"
    }
  }
}
```

#### Authentication

**Providers available via**:
1. `/connect` command in TUI (interactive setup)
2. Environment variables (provider-specific)
3. Managed settings (organization-level)

#### OpenCode Zen (curated models)

- **Access**: Run `/connect` in TUI, select OpenCode Zen
- **What**: Pre-tested, verified models across providers
- **Purpose**: Simplified provider/model selection for users

**Sources:**
- https://opencode.ai/docs/providers (provider configuration, authentication)
- https://opencode.ai/docs (introduction, zen model list)

---

### Configuration (opencode.json / opencode.jsonc)

#### Format

- **JSON**: `opencode.json` (strict JSON)
- **JSONC**: `opencode.jsonc` (JSON with comments)
- **Schema**: Available at `https://opencode.ai/config.json` (for autocomplete in VS Code, Cursor, etc.)

#### Config file locations and precedence

1. **Remote config** (`.well-known/opencode` endpoint) — organizational defaults
2. **Global config** (`~/.config/opencode/opencode.json`)
3. **Custom config** (`OPENCODE_CONFIG` env var)
4. **Project config** (`opencode.json` in project root)
5. **`.opencode` directories** (agents, commands, plugins auto-discovered)
6. **Inline config** (`OPENCODE_CONFIG_CONTENT` env var)
7. **Managed config files** (system directories: `/Library/Application Support/`, `/etc/`, `%ProgramData%`)
8. **macOS managed preferences** (MDM, highest priority, not user-overridable)

**Note**: Configs are MERGED, not replaced; later sources override conflicts for scalars; arrays merge and de-dupe; objects deep-merge

#### Top-level configuration keys

| Key | Type | Description |
|-----|------|-------------|
| `$schema` | string | Point to schema: `https://opencode.ai/config.json` |
| `model` | string | Default model (e.g., `anthropic/claude-sonnet-4-20250514`) |
| `small_model` | string | Model for lightweight tasks (title generation) |
| `agent` | object | Agent definitions and configurations |
| `default_agent` | string | Default primary agent (`build` if unset) |
| `command` | object | Custom command definitions |
| `permission` | object | Global tool permissions |
| `tools` | object | Tool enable/disable (glob patterns supported) |
| `mcp` | object | MCP server configuration |
| `instructions` | array | File paths/URLs for custom rules |
| `provider` | object | Provider-specific options (timeout, region, etc.) |
| `server` | object | Server config for `opencode serve` / `opencode web` |
| `theme` | string | UI theme (in `tui.json`; deprecated in `opencode.json`) |
| `keybinds` | object | Custom keybinds (in `tui.json`; deprecated in `opencode.json`) |
| `tui` | object | TUI settings (deprecated; use `tui.json` instead) |
| `formatters` | object | Code formatter configuration |
| `compaction` | object | Context compaction: `{auto: true, prune: true, reserved: 10000}` |
| `watcher` | object | File watcher ignore patterns: `{ignore: ["node_modules/**"]}` |
| `plugins` | array | NPM plugins to load: `["opencode-helicone-session"]` |
| `enabled_providers` | array | Allowlist of providers (all others ignored) |
| `disabled_providers` | array | Blocklist of providers |
| `snapshot` | boolean | Enable/disable change tracking (default: true) |
| `autoupdate` | boolean or string | Auto-update behavior: true, false, or `"notify"` |
| `share` | string | Sharing mode: `manual`, `auto`, `disabled` |
| `experimental` | object | Experimental features (unstable, may change) |

#### Variable substitution in config

**Environment variables**:
```json
{
  "model": "{env:OPENCODE_MODEL}",
  "provider": {
    "anthropic": {
      "options": {
        "apiKey": "{env:ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

**File contents**:
```json
{
  "instructions": ["./custom-instructions.md"],
  "provider": {
    "openai": {
      "options": {
        "apiKey": "{file:~/.secrets/openai-key}"
      }
    }
  }
}
```

#### Server configuration (for `opencode serve` / `opencode web`)

```json
{
  "server": {
    "port": 4096,
    "hostname": "0.0.0.0",
    "mdns": true,
    "mdnsDomain": "myproject.local",
    "cors": ["http://localhost:5173", "https://app.example.com"]
  }
}
```

**Fields**:
- `port`: Port to listen on
- `hostname`: Hostname to bind to
- `mdns`: Enable mDNS service discovery
- `mdnsDomain`: Custom mDNS domain (default: `opencode.local`)
- `cors`: Additional CORS origins (must be full URLs with scheme + host + optional port)

#### Managed settings on macOS (via MDM)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadType</key>
      <string>ai.opencode.managed</string>
      <key>PayloadIdentifier</key>
      <string>com.example.opencode.config</string>
      <key>PayloadUUID</key>
      <string>GENERATE-UUID</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>share</key>
      <string>disabled</string>
      <key>server</key>
      <dict>
        <key>hostname</key>
        <string>127.0.0.1</string>
      </dict>
      <key>permission</key>
      <dict>
        <key>*</key>
        <string>ask</string>
        <key>bash</key>
        <dict>
          <key>*</key>
          <string>ask</string>
          <key>rm -rf *</key>
          <string>deny</string>
        </dict>
      </dict>
    </dict>
  </array>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadIdentifier</key>
  <string>com.example.opencode</string>
  <key>PayloadUUID</key>
  <string>GENERATE-UUID</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
</dict>
</plist>
```

**Deployment via**:
- Jamf Pro: Computers > Configuration Profiles > Upload
- FleetDM: Add `.mobileconfig` to gitops repo
- Kandji: Deploy to target devices

#### TUI configuration (tui.json / tui.jsonc)

```json
{
  "$schema": "https://opencode.ai/tui.json",
  "scroll_speed": 3,
  "scroll_acceleration": {
    "enabled": true
  },
  "diff_style": "auto",
  "mouse": true,
  "theme": "tokyonight"
}
```

**Sources:**
- https://opencode.ai/docs/config (complete config reference, all keys, locations, precedence, examples)

---

## Cross-CLI feature matrix

| Feature | Claude Code | OpenCode | Notes |
|---------|-------------|----------|-------|
| **Sub-agents/Custom agents** | ✅ `.claude/agents/<name>.md` with YAML frontmatter | ✅ `opencode.json` `agent` field or `.opencode/agents/<name>.md` | Both support full markdown agent bodies |
| **Skills** | ✅ `.claude/skills/<name>/SKILL.md` with supporting files | ✅ `.opencode/skills/<name>/SKILL.md` (Agent Skills standard) | Identical format; both optional supporting files |
| **Slash commands** | ✅ `/skill-name` (merged with skills); `.claude/commands/` | ✅ `/<command-name>` via `opencode.json` or `.opencode/commands/` | Same invocation pattern; OpenCode separates command from skill definitions |
| **Hooks** | ✅ 25+ events, 4 handler types, extensive matcher system | ❌ NOT documented or supported | Critical difference: OpenCode has no hook mechanism |
| **Plugins** | ✅ `.claude-plugin/plugin.json` with agents/skills/hooks/MCP/LSP | ✅ `.opencode/plugins/` with agents/commands/MCP (no hooks/LSP documented) | Claude Code plugins more feature-rich |
| **MCP servers** | ✅ `.mcp.json` or `claude mcp add` CLI; HTTP/SSE/stdio; OAuth | ✅ `opencode.json` `mcp` field or CLI; HTTP/stdio; OAuth | Both support same transports (SSE deprecated in Claude Code) |
| **Agent memory** | ✅ Auto-memory at `~/.claude/projects/<project>/memory/` | ❌ No persistent memory; rules static | Major difference: Claude Code persists learnings across sessions |
| **Per-agent model override** | ✅ `model:` field in agent frontmatter | ✅ `model:` field in agent config | Both support full model IDs |
| **Per-agent tool restriction** | ✅ `tools:`, `disallowedTools:`, `permissionMode:` fields | ✅ `permission:` object with tool-specific rules | Different syntax; Claude Code uses modes, OpenCode uses granular permissions |
| **Global config file** | `CLAUDE.md` | `AGENTS.md` (or `CLAUDE.md` fallback) | OpenCode supports Claude Code fallback for compatibility |
| **Settings schema** | JSON schema at `schemastore.org` | JSON schema at `opencode.ai/config.json` | Both provide autocomplete support |
| **Managed settings** | ✅ File-based + macOS/Windows/Linux MDM | ✅ File-based + macOS MDM (Windows via plist equivalent) | Claude Code has broader MDM support |
| **Provider support** | Anthropic, Bedrock, Vertex, Foundry, GitHub Copilot | Anthropic, OpenAI, Gemini, Bedrock, Azure, custom local | OpenCode supports more open-source/commercial providers |
| **Config format** | JSON (`settings.json`) | JSON/JSONC (`opencode.json`, `opencode.jsonc`) | OpenCode supports comments in JSON config |
| **Config locations** | `~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json` | `~/.config/opencode/opencode.json`, `opencode.json` | OpenCode uses standard XDG directories |
| **Agent frontmatter fields** | `name`, `description`, `model`, `tools`, `disallowedTools`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt` | `description`, `mode`, `temperature`, `model`, `prompt`, `steps`, `disable`, `permission`, `color`, `top_p`, `hidden`, `task` | Different fields reflect different design philosophies |
| **Context compaction** | Supported (auto or manual `/compact`) | ✅ Supported: `compaction: {auto, prune, reserved}` | Both manage context automatically |
| **Extended thinking** | ✅ `alwaysThinkingEnabled` setting | ❌ NOT documented | Claude Code explicitly supports extended/thinking mode |

---

## Implications for agent-notes engine

**1. Hooks system is Claude Code-exclusive and non-trivial to port**

Claude Code documents 25+ hook events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart/Stop, Elicitation, FileChanged, ConfigChange, hooks in skill/agent frontmatter, etc.) with 4 handler types (command, HTTP, prompt, agent), matcher patterns, exit code behavior, and full JSON I/O schema. OpenCode has **zero documented hooks mechanism**. 

**Engine implication**: When translating Claude Code configs to OpenCode, the code generator MUST:
- Detect all hook configurations (in `settings.json`, plugin `hooks/hooks.json`, skill/agent frontmatter)
- Either strip them silently (if non-critical) or raise a warning that OpenCode cannot support them
- Document to user which hook functionality will be lost

**2. Agent memory is Claude Code-exclusive; OpenCode has static rules only**

Claude Code persists auto-memory at `~/.claude/projects/<project>/memory/MEMORY.md` across sessions, supports `## Memory` sections in agent frontmatter/bodies, and maintains subagent-specific memory directories. OpenCode has **no persistent memory mechanism**; `AGENTS.md` rules are purely static.

**Engine implication**: When generating OpenCode configs:
- Strip `## Memory` sections from imported CLAUDE.md files
- Remove or comment-out any instructions referencing memory persistence (e.g., "remember this pattern for next session")
- Alert user that learned patterns won't carry forward between sessions in OpenCode
- For critical learnings, suggest moving them to static AGENTS.md

**3. Permission model fundamentally differs; direct 1:1 translation impossible**

Claude Code uses agent-level `permissionMode:` field (enum: default, acceptEdits, auto, dontAsk, bypassPermissions, plan) which sets session-wide behavior, plus optional tool-specific rules. OpenCode uses granular tool-level `permission: {edit: "ask|allow|deny", bash: {...}, webfetch: "ask|allow|deny"}` with glob pattern support for subcommands.

**Engine implication**: Config translator must implement a strategy for mapping modes to granular rules:
- `bypassPermissions` (Claude Code) → `{edit: "allow", bash: "*: allow", webfetch: "allow"}` (OpenCode)
- `acceptEdits` (Claude Code) → `{edit: "allow"}` (OpenCode)
- `auto` (Claude Code) → No direct equivalent; OpenCode has no auto-classification feature documented
- `plan` (Claude Code) → `{edit: "deny", bash: "deny", webfetch: "deny"}` (OpenCode approximation)
- Default/ask modes → `{*: "ask"}` (OpenCode)

**4. MCP configuration syntax differs in detail; both support same transports**

Claude Code: `claude mcp add --transport http <name> <url>` (CLI-first); configuration in `.mcp.json` with flat structure.
OpenCode: Direct `opencode.json` `mcp` field (JSON-first); field names differ (`command` vs `args` array structure).

**Engine implication**: Config translator must normalize between formats; parsing `claude mcp add` CLI commands and converting to JSON, or vice versa. Key difference: option ordering matters in Claude Code (`--transport` before name, `--` before command); OpenCode is fully declarative JSON.

**5. Model ID formats differ by provider; OpenCode requires `provider/model-id` always**

Claude Code accepts model aliases (`sonnet`, `opus`, `haiku`) or full IDs (`claude-sonnet-4-6`). OpenCode **always** requires `provider/model-id` format (e.g., `anthropic/claude-sonnet-4-20250514`). Third-party providers differ: Claude Code supports GitHub Copilot; OpenCode lists OpenAI, Gemini, Bedrock, Azure.

**Engine implication**: When translating model overrides:
- Detect source format (alias vs full ID vs provider/model)
- For OpenCode targets, always convert to `provider/model-id`
- Map provider aliases: `anthropic` (both), `bedrock` (both), `vertex` (Claude Code) → `google` (OpenCode), `foundry` (Claude Code only), `openai` (OpenCode), custom local (OpenCode)

**6. Installation and config paths differ across all platforms and CLIs**

Claude Code: `~/.claude/settings.json`, `.claude/` local directories, managed paths: `/Library/Application Support/ClaudeCode/`, `/etc/claude-code/`, `C:\Program Files\ClaudeCode\`
OpenCode: `~/.config/opencode/`, managed paths: `/Library/Application Support/opencode/`, `/etc/opencode/`, `%ProgramData%\opencode`

**Engine implication**: Config generator must:
- Detect target CLI before generating paths
- Use correct home directory expansion (`~` → user home) per platform
- Use correct managed settings paths per OS
- Validate paths don't conflict with other tools

**7. Managed settings deployment differs significantly**

Claude Code: Supports macOS/Windows/Linux MDM in addition to file-based; Windows registry-based MDM (`HKLM\SOFTWARE\Policies\ClaudeCode`).
OpenCode: macOS `.mobileconfig` via standard MDM; file-based on Linux/Windows (documented but less comprehensive than Claude Code).

**Engine implication**: Enterprise deployment scripts must:
- Detect platform (macOS, Windows, Linux)
- For macOS: generate `.mobileconfig` with `ai.opencode.managed` PayloadType for OpenCode; `com.anthropic.claudecode` for Claude Code
- For Windows: Claude Code supports registry-based MDM; OpenCode file-based only
- For Linux: Both file-based in `/etc/`; OpenCode uses `/etc/opencode/`, Claude Code uses `/etc/claude-code/`

**8. Skills and commands are conceptually different in OpenCode**

Claude Code merged `.claude/commands/` into skills (both create `/` commands); plugins create `/plugin-name:skill-name` (namespaced).
OpenCode keeps commands and skills separate: `commands` field in `opencode.json` or `.opencode/commands/` (flat), skills in `.opencode/skills/` (directories with `SKILL.md`).

**Engine implication**: When generating OpenCode:
- Decide per-item: is this a command (reusable prompt) or skill (multi-file knowledge)?
- Commands → `opencode.json` `command` field or `.opencode/commands/<name>.md`
- Skills → `.opencode/skills/<name>/SKILL.md`
- Plugin namespacing is automatic; no manual adjustment needed

**9. No subagent spawning mechanism documented for OpenCode**

Claude Code has explicit `Agent(agent-type)` tool syntax in permissions and documented agent teams with `SendMessage` tool for subagent communication. OpenCode documentation shows automatic delegation (agent decides when to use which subagent) and `@agent-name` mention syntax, but **no explicit agent spawning/coordination tool** documented.

**Engine implication**: Multi-agent workflows designed for Claude Code may not be portable to OpenCode without significant redesign. Features requiring direct subagent control or inter-agent messaging cannot be reliably translated.

**10. Plugin security and capabilities differ**

Claude Code plugins:
- Can bundle agents, skills, commands, **hooks**, MCP servers, LSP servers, monitoring
- Hook/MCP/permission restrictions prevent some features in plugin context
- Force-enable via managed settings `enabledPlugins`

OpenCode plugins:
- Can bundle agents, commands, MCP servers (hooks/LSP **not documented**)
- Simpler trust model
- Namespace all commands as `plugin-name:command-name` (unlike Claude Code skills)

**Engine implication**: Plugin generation requires CLI-specific templates. A plugin designed for Claude Code with hooks and LSP cannot be ported to OpenCode without removing those features.

---

## Document metadata

**Compilation date**: 2026-04-22
**Sources catalogued**: 15 official documentation pages (Claude Code docs.claude.com, OpenCode opencode.ai)
**Total configuration fields documented**: 150+ (Claude Code settings.json, OpenCode config)
**Hook events covered**: 25 (Claude Code only)
**Agent frontmatter fields covered**: 30+ combined
**Cross-platform paths documented**: 12+ per CLI
**Verified ambiguities/gaps**: 3 (marked UNVERIFIED in text where applicable)

**Notes for engine developers**:
- This catalogue is a frozen snapshot of official documentation as of 2026-04-22
- New CLI features may not be captured; refresh research periodically
- OpenCode documentation is thinner than Claude Code; ambiguities noted explicitly
- MCP/OAuth behavior is complex; test thoroughly before release
- Plugin security differs; validate sandboxing assumptions per CLI
