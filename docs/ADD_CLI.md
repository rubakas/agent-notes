# Adding a New CLI Backend

This guide shows how to add support for a new AI CLI (e.g., Cursor, GitHub Copilot Desktop, or a custom tool) to agent-notes. The architecture is **YAML-driven and extensible**: adding a new CLI requires zero Python changes for most cases.

---

## Section 1: What is a CLI Backend?

A **CLI backend** represents an AI development tool that agent-notes can configure. It's defined by a dataclass with these fields:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `name` | string | Unique identifier (lowercase, no spaces) | `"cursor"` |
| `label` | string | Display name shown in CLI and docs | `"Cursor"` |
| `global_home` | Path | Home directory (expands `~`) | `~/.cursor` |
| `local_dir` | string | Relative directory in projects | `.cursor` |
| `layout` | dict | Directory structure for components | `{"agents": "agents/", "skills": "skills/"}` |
| `features` | dict | Feature flags and template names | `{"agents": true, "frontmatter": "cursor"}` |
| `global_template` | Optional[str] | Global config template filename | `"global-cursor.md"` |
| `accepted_providers` | tuple[str, ...] | Model provider priority order | `("openai", "anthropic")` |
| `exclude_flag` (optional) | string | CLI-specific exclude mechanism | `"cursor_exclude"` |
| `strip_memory_section` (optional) | bool | Whether to strip memory sections | `false` |

**Key concepts:**
- **`accepted_providers`** determines which AI model services the CLI can use. Agent-notes matches this against a model's `aliases` (e.g., `{"openai": "gpt-5", "anthropic": "claude-opus-4-7"}`). The first provider in the CLI's list that has a matching alias is selected.
- **`features`** is a flexible dict. Core flags: `agents`, `skills`, `rules`, `commands`, `memory`, `frontmatter`. The `frontmatter` value is either a template name (→ `data/templates/frontmatter/{name}.py`) or `null` for config-only CLIs (no agents).
- **Config-only CLIs** (like GitHub Copilot, which only supports a `.md` config file) set `agents: false, skills: false, frontmatter: null`. They still appear in the installer but skip agent generation.

---

## Section 2: Step-by-Step — Create `agent_notes/data/cli/cursor.yaml`

### Step 2.1: Create the YAML descriptor

Create `agent_notes/data/cli/cursor.yaml`:

```yaml
name: cursor
label: Cursor
global_home: ~/.cursor
local_dir: .cursor
layout:
  agents: agents/
  skills: skills/
  rules: rules/
  commands: commands/
  config: CURSOR.md
  settings: settings.json
  memory: agent-memory/
features:
  agents: true
  skills: true
  rules: true
  commands: true
  memory: true
  frontmatter: cursor
  supports_symlink: true
global_template: global-cursor.md
accepted_providers: [anthropic, openai]
```

**Field explanations:**
- **`name: cursor`** — Unique identifier (used in `wizard`, `list clis`, state.json).
- **`label: Cursor`** — Shown in UI: `"Which CLI do you use? [] Cursor"`.
- **`global_home: ~/.cursor`** — Where users' global Cursor config lives. Expands to `$HOME/.cursor`. Agent-notes creates this if needed.
- **`local_dir: .cursor`** — Relative directory in projects. If user installs locally in `/my/project`, files go to `/my/project/.cursor/`.
- **`layout`** — Maps component type to subdirectory. `agents: agents/` means agent files go in `~/.cursor/agents/`.
- **`features`**:
  - `agents: true` — Cursor supports agent files.
  - `frontmatter: cursor` — Use `data/templates/frontmatter/cursor.py` to generate YAML headers.
  - `supports_symlink: true` — Cursor allows symlinked files (alternatively: `false` to force copy mode).
  - Other keys are informational (may be checked by future install logic).
- **`global_template: global-cursor.md`** — Template file copied to `~/.cursor/CURSOR.md` (global config). Lives in `data/globals/`.
- **`accepted_providers: [anthropic, openai]`** — Priority order. If a model has aliases for both `anthropic` and `openai`, Cursor will use the `anthropic` one. Anthropic models first, then fallback to OpenAI.

### Step 2.2: Verify the file is valid YAML

```bash
python3 -c "import yaml; yaml.safe_load(open('agent_notes/data/cli/cursor.yaml'))"
# Should produce no output (success). Any error will print.
```

### Step 2.3: Test registry loading

```bash
python3 << 'EOF'
from agent_notes.cli_backend import load_registry
from pathlib import Path

registry = load_registry(Path("agent_notes/data/cli"))
for backend in registry.all():
    print(f"{backend.name:15} | {backend.label:20} | {backend.global_home}")
EOF
```

Expected output (includes your new cursor):
```
claude          | Claude Code      | /Users/en3e/.claude
copilot         | GitHub Copilot   | /Users/en3e/.github
cursor          | Cursor           | /Users/en3e/.cursor
opencode        | OpenCode         | /Users/en3e/.config/opencode
```

---

## Section 3: Frontmatter Template

If **`features.frontmatter` is NOT `null`**, agent-notes needs a Python template to generate the YAML frontmatter for agent files.

### When to add a template

- **Different frontmatter format from Claude/OpenCode?** → Add a new template.
- **Same format (just YAML with standard fields)?** → Reuse existing template or copy one.

### Create `agent_notes/data/templates/frontmatter/cursor.py`

```python
"""Cursor agent frontmatter generator.

Renders YAML frontmatter for Cursor agents based on the agent's config
and the selected model.
"""


def render(ctx: dict) -> str:
    """Render YAML frontmatter for a Cursor agent.

    Args:
        ctx: Context dict with keys:
            - agent_name (str): e.g. "lead"
            - agent (dict): from agents.yaml[agent_name]
            - model_id (str): resolved model alias for the provider (e.g. "claude-opus-4-7")
            - cli (CLIBackend): the Cursor backend
            - prompt (str): the prompt body (system instructions)

    Returns:
        YAML frontmatter as string, including --- delimiters.
    """
    lines = ["---"]
    lines.append(f"name: {ctx['agent_name']}")
    lines.append(f"description: {ctx['agent']['description']}")
    lines.append(f"model: {ctx['model_id']}")
    
    # Cursor-specific config from agents.yaml
    cursor_cfg = ctx['agent'].get('cursor', {})
    if 'tools' in cursor_cfg:
        lines.append(f"tools: {cursor_cfg['tools']}")
    if 'memory' in cursor_cfg:
        lines.append(f"memory: {cursor_cfg['memory']}")
    if 'color' in ctx['agent']:
        lines.append(f"color: {ctx['agent']['color']}")
    
    lines.append("---")
    return "\n".join(lines)


def post_process(prompt: str, ctx: dict) -> str:
    """Optional: transform the prompt body after frontmatter.
    
    For Cursor, if it doesn't support ## Memory sections, strip them.
    Otherwise return as-is.
    
    Args:
        prompt: The agent's prompt body (system instructions).
        ctx: Same context dict as render().
    
    Returns:
        Modified prompt (or unchanged if no processing needed).
    """
    # If Cursor doesn't support agent memory, strip the ## Memory section:
    # return _strip_memory_section(prompt)
    
    # Otherwise, for parity with Claude Code format:
    return prompt
```

**Key points:**
- `render()` must return the frontmatter **with `---` delimiters** at start and end.
- `post_process()` is optional; return the prompt unchanged if no modification is needed.
- Use `ctx['agent'].get('<cli_name>', {})` to access CLI-specific config from `agents.yaml`. Example:
  ```yaml
  # agents.yaml
  lead:
    role: orchestrator
    description: "..."
    cursor:
      tools: "read, write, bash"
      memory: user
  ```

### No template needed?

If Cursor uses the **exact same frontmatter format as Claude Code**, you can skip the template:

```yaml
# agent_notes/data/cli/cursor.yaml
features:
  frontmatter: claude  # Reuse Claude's template
```

---

## Section 4: Verify with Commands

### 4.1 List CLIs

```bash
agent-notes list clis
```

Expected output includes:
```
CLIs (4):
  claude    Claude Code           → ~/.claude
  copilot   GitHub Copilot        → ~/.github
  cursor    Cursor                → ~/.cursor
  opencode  OpenCode              → ~/.config/opencode
```

### 4.2 Run the wizard

```bash
agent-notes install
```

Wizard should show:
```
Step 1 of 4: Which CLI(s) do you use?
  [✓] Claude Code
  [ ] Cursor          ← your new CLI appears here
  [✓] OpenCode
  [ ] GitHub Copilot
```

### 4.3 Install test (optional)

To fully test, proceed through the wizard (or abort). The wizard will validate:
- Cursor YAML loads correctly.
- Cursor's `accepted_providers` match at least one available model.
- If `frontmatter: cursor`, the `data/templates/frontmatter/cursor.py` template loads and runs.

---

## Section 5: Common Pitfalls

### Pitfall 1: `accepted_providers` doesn't match any model

**Problem:** You set `accepted_providers: [nonexistent-ai]`, but no model has an alias for "nonexistent-ai".

**Symptom:** Wizard works until step 2 (model selection), where Cursor shows no available models.

**Solution:** Check available aliases:
```bash
python3 << 'EOF'
from agent_notes.model_registry import load_model_registry

registry = load_model_registry()
for model in registry.all():
    print(f"{model.id}: {list(model.aliases.keys())}")
EOF
```

Example output:
```
claude-haiku-4-5: ['anthropic', 'github-copilot']
claude-opus-4-7: ['anthropic', 'github-copilot']
claude-sonnet-4: ['anthropic', 'github-copilot']
```

Use providers that exist. For Cursor to support multiple model sources, add aliases to model YAMLs (see `docs/ADD_MODEL.md`).

### Pitfall 2: Frontmatter template not found

**Problem:** YAML says `frontmatter: cursor` but `data/templates/frontmatter/cursor.py` doesn't exist.

**Symptom:** Installer crashes during agent generation with `ModuleNotFoundError: No module named 'agent_notes.data.templates.frontmatter.cursor'`.

**Solution:**
1. Create the template (Section 3 above), OR
2. Set `frontmatter: claude` (reuse existing), OR
3. Set `frontmatter: null` if CLI doesn't support agents.

### Pitfall 3: YAML field typos

**Problem:** You write `global_home_dir` instead of `global_home`.

**Symptom:** Registry loader raises `ValueError: Missing required field 'global_home'`.

**Solution:** Check required fields against the CLIBackend dataclass:
```
name, label, global_home, local_dir, layout, features
```

Optional fields:
```
global_template, exclude_flag, strip_memory_section, settings_template, accepted_providers
```

### Pitfall 4: `layout` doesn't match CLI's actual structure

**Problem:** You set `layout.agents: agent-files/` but Cursor's docs say agents go in `agents/`.

**Symptom:** Installer writes files to wrong paths; user's Cursor doesn't find the agents.

**Solution:** Refer to the CLI's official docs. Copy-paste from an existing working CLI YAML if the structure is similar.

### Pitfall 5: Frontmatter template uses wrong context fields

**Problem:** Template tries `ctx['agent']['cli_specific_field']` but agent only has `description`, `role`, etc.

**Symptom:** Installer crashes with `KeyError` during agent generation.

**Solution:**
- Check `agents.yaml` to see what fields agents actually have. Common fields:
  ```yaml
  lead:
    role: orchestrator            # always present
    description: "..."            # required
    mode: primary                 # optional
    <cli_name>:                   # optional per-CLI config
      tools: "..."
      memory: user
  ```
- Use `.get()` with defaults:
  ```python
  tools = ctx['agent'].get('cursor', {}).get('tools', '')
  ```

---

## Checklist

- [ ] Created `agent_notes/data/cli/cursor.yaml`
- [ ] All required fields present: `name`, `label`, `global_home`, `local_dir`, `layout`, `features`
- [ ] `accepted_providers` matches at least one model (verify with `agent-notes list models`)
- [ ] If `features.frontmatter` is not `null`, created `agent_notes/data/templates/frontmatter/cursor.py`
- [ ] If `global_template` is set, created `agent_notes/data/globals/cursor.md`
- [ ] Ran `agent-notes list clis` and saw the new CLI
- [ ] Ran `agent-notes install` and wizard offered the new CLI in step 1
- [ ] Tested model selection in wizard step 2 (shows available models)
- [ ] No errors during agent generation (if you proceeded with install)

---

## Next Steps

- **Add more models** if Cursor supports providers not yet in the registry: see `docs/ADD_MODEL.md`.
- **Customize agents.yaml** if Cursor needs different CLI-specific config than Claude Code. Add a `cursor:` section to agents that need special handling.
- **Update CLI_CAPABILITIES.md** with Cursor's features so future maintainers know what it supports.

