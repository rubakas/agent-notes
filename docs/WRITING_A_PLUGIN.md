# Writing a Plugin

This guide shows how to author an agent-notes plugin — a toggleable subsystem that users can enable or disable post-install.

---

## Important: Two Meanings of "Plugin"

**Do NOT confuse these:**

1. **Claude Code plugin** (`.claude-plugin/` distribution artifact) — A packaged bundle of agents and skills delivered via the Claude Code marketplace. Installed via method 3 in README. See the "Plugin (limited functionality)" section in README.

2. **Agent-notes plugin** (this document) — An **internal toggleable subsystem** that users enable/disable with `agent-notes plugins enable|disable`. Built into agent-notes via `agent_notes/data/plugins/`, controlled by user config.

**Quick test:** If the user types `agent-notes plugins list`, they're looking at agent-notes plugins (this document). If they're installing `.claude-plugin/` from the marketplace, that's a Claude Code plugin (README).

---

## Section 1: Understand the Plugin Model

### What a Plugin Is

A plugin is a declarative YAML manifest (`plugin.yaml`) that tells agent-notes to install:
- **hooks** — shell commands to run at SessionStart, Stop, PreToolUse, or PreCompact events
- **allow-entries** — Bash/Read/Write/Edit permissions in Claude's settings.json
- **skills, agents, rules, includes** — optional registrations (future-proofing)

Users enable the plugin during install or later with:
```bash
agent-notes plugins enable <name>
agent-notes install  # apply changes
```

When disabled, all the plugin's contributions are **actively removed** from Claude's settings.json.

### Example: cost-report Plugin

The only built-in plugin today is `cost-report`. Here's its manifest at `agent_notes/data/plugins/cost-report/plugin.yaml`:

```yaml
name: cost-report
description: Emit a per-session token cost report at the Stop hook
default: off
includes: [cost_reporting]
hooks:
  - {event: Stop, command: "agent-notes cost-report", requires: stop_hook}
allow:
  - {value: "Bash(agent-notes cost-report)", requires: allow_entries}
```

**What this means:**
- Default state: **off** (users must enable it)
- When enabled:
  - Installs a Stop hook that runs `agent-notes cost-report` at session end
  - Grants Bash permission for the command `"Bash(agent-notes cost-report)"`
  - Both are gated on backend support (`stop_hook` / `allow_entries` capabilities)
- When disabled: both hook and allow-entry are removed from settings.json

---

## Section 2: Plugin YAML Schema

### Full Manifest Example

```yaml
name: my-plugin
description: What this plugin does
default: off                           # "on" or "off" (string, not boolean)
stability: stable                      # optional: "stable" (visible, default); "wip" (hidden unless AGENT_NOTES_ENABLE_WIP)

# Optional contribution surfaces (all default to empty if omitted):
skills: [skill1, skill2]               # Skill names from data/skills/
agents: [agent1, agent2]               # Agent names from data/agents/agents.yaml
rules: [rule1, rule2]                  # Rule names from data/rules/
includes: [include1, include2]         # Include names for wizard steps

# Hooks: events run in Claude settings.json
hooks:
  - event: SessionStart                # Event: SessionStart, Stop, PreToolUse, PreCompact
    command: "my-cli-command"          # Command line to run
    matcher: "Read|Bash"                # (optional) tool matcher for PreToolUse
    requires: stop_hook                # (optional) backend capability gate

# Allow entries: Bash/Read/Write/Edit permissions
allow:
  - value: "Bash(my-cli-command)"      # Permission pattern
    requires: allow_entries            # (optional) backend capability gate
```

### Field Reference

#### Required Fields

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `name` | string | Plugin identifier (lowercase, hyphens) | `"cost-report"` |
| `description` | string | User-visible description shown in `plugins list` | `"Emit a per-session token cost report..."` |
| `default` | string | Default on/off state (`"on"` or `"off"`) | `"off"` |

#### Optional Fields

| Field | Type | Purpose | Default |
|-------|------|---------|---------|
| `skills` | list[string] | Skill names to register | `[]` |
| `agents` | list[string] | Agent names to register | `[]` |
| `rules` | list[string] | Rule names to register | `[]` |
| `includes` | list[string] | Include names for wizard | `[]` |
| `hooks` | list[PluginHook] | Hook definitions | `[]` |
| `allow` | list[PluginAllow] | Permission entries | `[]` |
| `stability` | string | Visibility: `"stable"` (shown) or `"wip"` (hidden unless AGENT_NOTES_ENABLE_WIP) | `"stable"` |

#### Hook Fields (`hooks` list)

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `event` | string | Yes | Hook event: `SessionStart`, `Stop`, `PreToolUse`, `PreCompact` |
| `command` | string | Yes | Shell command string (e.g., `"agent-notes cost-report"`) |
| `matcher` | string | No | Tool matcher for `PreToolUse` (e.g., `"Read\|Bash\|Grep"`) |
| `requires` | string | No | Backend capability gate (e.g., `"stop_hook"`, `"allow_entries"`, `"pretooluse_hooks"`) |

#### Allow Fields (`allow` list)

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `value` | string | Yes | Permission pattern (e.g., `"Bash(agent-notes cost-report)"`) |
| `requires` | string | No | Backend capability gate |

---

## Section 3: Hook Events and Matchers

### Hook Events

- **SessionStart** — Runs when a Claude session begins. Used to inject context, check state, etc.
- **Stop** — Runs when a session ends. Used for cleanup, reporting (e.g., cost-report).
- **PreToolUse** — Runs before a tool is called. Scoped via `matcher` to specific tools.
- **PreCompact** — Runs before Claude compacts/truncates the conversation. Used for memory sync.

### PreToolUse Matcher

For `PreToolUse` events, use the `matcher` field to scope the hook to specific tools:

```yaml
hooks:
  - event: PreToolUse
    command: "agent-notes hook guard-credentials"
    matcher: "Read|Bash|Grep"          # Only run for Read, Bash, or Grep tools
```

Matchers are regex patterns matching tool names (exactly as they appear in the CLI). Omitting `matcher` (or leaving it empty) means "run for all PreToolUse calls".

### Backend Capability Gates

Each hook and allow-entry can declare an optional `requires` gate. The hook/entry is installed **only if the backend supports that capability**.

**Available gates:**
- `stop_hook` — Backend supports Stop hook (Claude: yes, OpenCode: yes, GitHub Copilot: no)
- `allow_entries` — Backend supports permission allow-list (Claude: yes, OpenCode: no, GitHub Copilot: no)
- `pretooluse_hooks` — Backend supports PreToolUse hooks (Claude: yes, OpenCode: yes, GitHub Copilot: no)

**Example:**
```yaml
hooks:
  - event: Stop
    command: "agent-notes cost-report"
    requires: stop_hook                # Skip on backends without Stop hook support
```

If a backend doesn't support the gate, the hook is silently skipped. This allows plugins to gracefully degrade.

---

## Section 4: Declarative Surfaces vs. install_hook Escape Hatch

### When to Use Declarative YAML

Use `hooks` and `allow` in `plugin.yaml` for:
- Single-purpose hooks that don't need complex initialization
- Hooks that may be conditionally installed based on backend support

**Example: cost-report**
```yaml
hooks:
  - event: Stop
    command: "agent-notes cost-report"
    requires: stop_hook
```

### When to Use install_hook Escape Hatch

The `install_hook` escape hatch (in `agent_notes/services/settings_writer.py`) is used for:
- Core infrastructure that must always be installed (no disable option)
- Hooks that need complex per-install setup (e.g., reading the current memory backend)
- Non-declarative sources (e.g., computed during install based on user config)

**Current escape-hatch users:**
- **Memory subsystem** — `install_memory_hooks()` reads the current memory backend and installs the right hooks (SessionStart/PreCompact for Obsidian, nothing for others)
- **Credential guard** — `Hooks.GUARD_CREDENTIALS` is installed unconditionally for backends that support `pretooluse_hooks`

**Why they're not plugins:**
- Memory is toggleable via `agent-notes config memory` but not via `plugins enable|disable` (backward-compatible config key)
- Credential guard is hardcoded core, never togglable — it protects the user from accidentally exposing credentials

**Rule:** If you're writing new escape-hatch code, document why it can't be declarative and mark it as temporary. Future work is to eliminate escape-hatches and move everything to declarative plugins.

---

## Section 5: Installation and Removal Flow

### When a Plugin is Enabled

1. User runs: `agent-notes plugins enable my-plugin`
2. CLI writes to user config: `enabled_plugins: {my-plugin: true}`
3. User runs: `agent-notes install`
4. At install time, `_apply_plugin_settings()` is called:
   - Loads the plugin manifest
   - For each hook: calls `install_hook(settings.json, event, command, matcher=...)`
   - For each allow-entry: calls `install_allow_entry(settings.json, value)`
5. Claude's `settings.json` now contains the plugin's contributions

### When a Plugin is Disabled

1. User runs: `agent-notes plugins disable my-plugin`
2. CLI writes to user config: `enabled_plugins: {my-plugin: false}`
3. User runs: `agent-notes install`
4. At install time, `_apply_plugin_settings()` is called:
   - For each hook: calls `remove_hook(settings.json, event, command)` — **actively removes it**
   - For each allow-entry: calls `remove_allow_entry(settings.json, value)` — **actively removes it**
5. Claude's `settings.json` no longer contains the plugin's contributions

---

## Section 6: Byte-Identity Discipline

A plugin **must not change `dist/` when at its default state**. This ensures that a build with the plugin at default matches a build without it.

### Why This Matters

Agent-notes is distributed as a wheel with pre-built `dist/` artifacts. If a plugin changes files in `dist/` when enabled, the byte-identical distribution guarantee breaks — different wheels would contain different `dist/` contents depending on build-time plugin state.

### The Rule

When all plugins use their **default** settings (cost-report: off, etc.), the resulting `dist/` **must be byte-identical** to a build where plugins don't exist.

This is enforced by the `scripts/dev/verify_dist_equiv.sh` script, which compares byte-identical build outputs between your baseline commit and the current state.

### How to Verify

After authoring a new plugin, verify byte-identity:

```bash
# Before adding your plugin, record a baseline:
git rev-parse HEAD  # e.g., abc1234

# Add your plugin, commit
git add agent_notes/data/plugins/my-plugin/
git commit -m "feat: add my-plugin"

# Verify byte-identity (from new commit, build with all defaults):
scripts/dev/verify_dist_equiv.sh abc1234
```

If the script reports differences, check:
1. Does your plugin's `default` match its actual default behavior?
2. Does your plugin contribute `skills`, `agents`, or `rules` that change the build output?
3. Are any of your `includes` being registered by default?

---

## Section 7: Creating a New Plugin — Step by Step

### Step 1: Create the Directory

```bash
mkdir -p agent_notes/data/plugins/my-plugin
```

### Step 2: Write plugin.yaml

Create `agent_notes/data/plugins/my-plugin/plugin.yaml`:

```yaml
name: my-plugin
description: A brief description of what this plugin does
default: off
hooks:
  - event: Stop
    command: "agent-notes hook my-plugin"
allow:
  - value: "Bash(agent-notes hook my-plugin)"
```

**Field checklist:**
- `name` matches directory name (`my-plugin`)
- `description` is clear and under 80 chars
- `default` is `"on"` or `"off"` (string)
- Hooks have `event` and `command` (required); `matcher` and `requires` optional
- Allow entries have `value` (required); `requires` optional

### Step 3: Implement the Hook Command

If your plugin declares a hook like `command: "agent-notes hook my-plugin"`, that command must exist and be handled by the CLI. Today, this means:

1. Add a handler in `agent_notes/commands/hook.py` (if it doesn't exist)
2. Wire it up in `cli.py` under a `hook` subcommand

Example for cost-report (the command is `agent-notes cost-report`, which is a standalone subcommand, not under `hook`):

```bash
# The hook command in plugin.yaml:
command: "agent-notes cost-report"

# Wired in cli.py:
elif args.command == "cost-report":
    from .commands.cost_report import cost_report
    cost_report()
```

### Step 4: Declare Contribution Surfaces (If Needed)

If your plugin contributes skills, agents, rules, or includes, add them:

```yaml
skills: [my-skill-1, my-skill-2]
agents: [my-agent-1]
rules: [my-rule-1]
includes: [my-include-1]
```

Each name must match an existing name in the registry. For skills, the name is the directory name in `agent_notes/data/skills/`. For agents, it's in `data/agents/agents.yaml`. Etc.

### Step 5: Verify with agent-notes plugins info

```bash
agent-notes plugins info my-plugin
```

Expected output:
```
my-plugin — A brief description of what this plugin does
  default:  off
  skills:   my-skill-1, my-skill-2
  agents:   my-agent-1
  rules:    my-rule-1
  includes: my-include-1
  hooks:    Stop
  allow:    Bash(agent-notes hook my-plugin)
```

### Step 6: Test Enable / Disable

```bash
# Enable the plugin
agent-notes plugins enable my-plugin

# Verify it's enabled
agent-notes plugins list
# Should show: "  my-plugin [on] ..."

# Install to apply changes
agent-notes install

# Verify hook is in settings.json
cat ~/.claude/settings.json | grep "agent-notes hook my-plugin"

# Disable the plugin
agent-notes plugins disable my-plugin

# Re-install
agent-notes install

# Verify hook is removed
cat ~/.claude/settings.json | grep "agent-notes hook my-plugin"
# Should NOT find it
```

### Step 7: Verify Byte-Identity

```bash
# From the commit before adding your plugin:
git rev-parse HEAD  # e.g., abc1234

# Add plugin, commit
git add agent_notes/data/plugins/my-plugin/
git commit -m "feat: add my-plugin"

# Verify (assuming it defaults to off and doesn't affect dist/):
scripts/dev/verify_dist_equiv.sh abc1234
```

---

## Section 8: Common Pitfalls

### Pitfall 1: `default` is a boolean instead of a string

**Problem:**
```yaml
default: false        # WRONG (boolean)
```

**Symptom:** YAML loader fails with `ValueError: 'default' must be on/off`

**Solution:**
```yaml
default: off          # RIGHT (string)
```

---

### Pitfall 2: Hook event name is wrong

**Problem:**
```yaml
hooks:
  - event: PostToolUse     # WRONG (not a real event)
    command: "..."
```

**Symptom:** Hook is silently ignored (malformed hook won't load).

**Solution:** Use one of: `SessionStart`, `Stop`, `PreToolUse`, `PreCompact`

---

### Pitfall 3: Plugin changes `dist/` when at default state

**Problem:** Your plugin has `default: off`, but enabling it modifies `data/agents/` or `data/skills/` in a way that changes the build output even when the plugin is off.

**Symptom:** `scripts/dev/verify_dist_equiv.sh` fails; byte-identity broken.

**Solution:** Ensure your `default` matches the actual default behavior. If your plugin contributes agents/skills, they should only be built when explicitly enabled.

---

### Pitfall 4: Forgetting to declare requires gate

**Problem:**
```yaml
hooks:
  - event: Stop
    command: "agent-notes cost-report"
    # Missing: requires: stop_hook
```

**Symptom:** Plugin tries to install Stop hook on GitHub Copilot (which doesn't support it). Hook silently fails.

**Solution:** Add the `requires` gate if your hook/allow uses a backend feature:
```yaml
hooks:
  - event: Stop
    command: "agent-notes cost-report"
    requires: stop_hook
```

---

### Pitfall 5: Using `requires` without checking backend support in code

**Problem:** You declare `requires: my_feature`, but backends don't actually have that capability defined.

**Symptom:** Hook never installs, even on backends that should support it.

**Solution:** First, add the capability to the backend definition in `data/cli/`. Check `test_cli_registry.py` for examples of how capabilities are tested.

---

## Section 9: Checklist

- [ ] Created `agent_notes/data/plugins/<name>/` directory
- [ ] Created `plugin.yaml` with required fields: `name`, `description`, `default`
- [ ] Verified `name` matches directory name (lowercase, hyphens)
- [ ] Verified `default` is a string: `"on"` or `"off"` (not boolean)
- [ ] If plugin has hooks: implemented the hook command and wired it in CLI
- [ ] If plugin uses backend capabilities: added `requires` gate to hooks/allow-entries
- [ ] Ran `agent-notes plugins info <name>` and verified output
- [ ] Tested `agent-notes plugins enable <name>` → `agent-notes install`
- [ ] Verified hook/allow-entry appears in `~/.claude/settings.json`
- [ ] Tested `agent-notes plugins disable <name>` → `agent-notes install`
- [ ] Verified hook/allow-entry is removed from `~/.claude/settings.json`
- [ ] Ran `scripts/dev/verify_dist_equiv.sh <baseline>` and verified byte-identity holds (if applicable)

---

## See Also

- `README.md` — Plugin toggle section (`agent-notes plugins list|enable|disable|info`)
- `docs/ARCHITECTURE.md` — Plugin layer design and escape-hatch rationale
- `agent_notes/domain/plugin.py` — `Plugin` and `PluginHook` dataclass definitions
- `agent_notes/registries/plugin_registry.py` — Plugin registry and manifest loader
- `agent_notes/data/plugins/cost-report/plugin.yaml` — Reference implementation
- `agent_notes/services/installer.py::_apply_plugin_settings()` — Plugin installation orchestration
