# Adding a New Role

This guide shows how to add a new role that agents can declare. Roles are **abstract responsibilities** (orchestrator, worker, scout, reasoner) that map to model tiers at install time.

---

## Section 1: Role Dataclass Fields

A **Role** is defined by these fields (stored in YAML):

| Field | Type | Required | Purpose | Example |
|-------|------|----------|---------|---------|
| `name` | string | **Yes** | Unique identifier (lowercase, no spaces) | `"specialist"` |
| `label` | string | **Yes** | Display name (title case) | `"Specialist"` |
| `description` | string | **Yes** | What this role does (1-2 sentences, used by wizard) | `"Deep expertise in specific domains. Medium reasoning."` |
| `typical_class` | string | **Yes** | Hint for wizard defaults | `"sonnet"`, `"opus"`, `"haiku"`, `"flash"` |
| `color` | string | No | Display color in UI | `"orange"`, `"blue"`, `"green"` |

**Key concepts:**

- **`name`** — Identifier used in:
  - `agents.yaml`: `lead: { role: specialist }`
  - Wizard step 2: `Specialist (...)` picker
  - Commands: `agent-notes set role specialist claude-sonnet-4`
  - state.json: `role_models: {specialist: "claude-sonnet-4"}`

- **`typical_class`** — Hints which model class the wizard should default-select for this role:
  - `"opus"` → high reasoning, planning, architecture
  - `"sonnet"` → balanced reasoning + execution (most roles)
  - `"haiku"` → fast, low reasoning, exploration
  - `"flash"` → ultra-fast, minimal reasoning (new tier)
  
  The wizard shows models with matching `class` as the `[*]` default during step 2.

- **`description`** — Shown in:
  - Wizard step 2: `Specialist (Deep expertise...)` — helps user understand what the role is for
  - `agent-notes list roles` output
  - Documentation (e.g., this guide)

- **`color`** (optional) — May be used by future UI enhancements. Current values: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan`.

---

## Section 2: Step-by-Step — Create `agent_notes/data/roles/specialist.yaml`

### Step 2.1: Create the YAML descriptor

Create `agent_notes/data/roles/specialist.yaml`:

```yaml
name: specialist
label: Specialist
description: Deep expertise in specific domains. Medium reasoning, high accuracy.
typical_class: sonnet
color: orange
```

**Field explanations:**

- **`name: specialist`** — Used in agents.yaml as `role: specialist`.
  - Must be lowercase, no spaces.
  - Typically matches a job description (coder, planner, explorer, debugger, specialist).

- **`label: Specialist`** — Shown in UI. Title case, human-readable.

- **`description: ...`** — Short explanation. Wizard shows this in step 2:
  ```
  Specialist (Deep expertise in specific domains. Medium reasoning, high accuracy.):
    1) [*] Claude Sonnet 4    (via anthropic)
    2) [ ] Claude Opus 4.7
  ```

- **`typical_class: sonnet`** — When user selects CLIs and proceeds to step 2:
  - Wizard filters models to those compatible with each CLI
  - Groups them by class
  - Checks model(s) with `class: sonnet` by default
  - User can uncheck and select different models
  
  This is just a hint — users can override.

- **`color: orange`** — Hint for future UI (e.g., status line indicators, role badges). No effect today.

### Step 2.2: Verify YAML is valid

```bash
python3 -c "import yaml; yaml.safe_load(open('agent_notes/data/roles/specialist.yaml'))"
# Should produce no output (success).
```

### Step 2.3: Test registry loading

```bash
python3 << 'EOF'
from agent_notes.role_registry import load_role_registry

registry = load_role_registry()
role = registry.get("specialist")
print(f"Name:           {role.name}")
print(f"Label:          {role.label}")
print(f"Description:    {role.description}")
print(f"Typical class:  {role.typical_class}")
print(f"Color:          {role.color}")
EOF
```

Expected output:
```
Name:           specialist
Label:          Specialist
Description:    Deep expertise in specific domains. Medium reasoning, high accuracy.
Typical class:  sonnet
Color:          orange
```

---

## Section 3: Assign Agents to the New Role

Once the role exists in the registry, assign agents to it by updating `agent_notes/data/agents/agents.yaml`.

### Example: Assign a new agent to the specialist role

```yaml
# agent_notes/data/agents/agents.yaml
agents:
  lead:
    role: orchestrator              # existing agent
    description: "Plans and delegates..."
    mode: primary
    claude: { tools: "..." }
  
  specialist:                        # NEW agent
    role: specialist                 # use the new role
    description: "Domain expert for complex implementation details"
    mode: primary
    claude:
      tools: "read, write, edit, bash"
      memory: user
```

**Or reassign an existing agent:**

```yaml
  coder:
    role: specialist                 # changed from "worker"
    description: "..."
```

### Field requirements

Agents in `agents.yaml` need:
- **`role: <role-name>`** — Must exist in `data/roles/` (e.g., `specialist`)
- **`description`** — Required; shown in UI and agent frontmatter
- **`<cli_name>`** — Per-CLI config (optional)
  - Example: `claude: { tools: "...", memory: "..." }`
  - Replaces old `tier:` field (removed in Phase 9)

**Example with multiple CLIs:**

```yaml
  lead:
    role: orchestrator
    description: "Team lead, delegates and plans"
    mode: primary
    claude:
      tools: read, write, edit, bash, grep, glob, webfetch
      memory: user
    opencode:
      permission: acceptEdits
```

### Verify agents reference existing roles

```bash
python3 << 'EOF'
import yaml
from agent_notes.role_registry import load_role_registry

# Load agents
agents_yaml = "agent_notes/data/agents/agents.yaml"
with open(agents_yaml) as f:
    agents_data = yaml.safe_load(f)
agents_config = agents_data.get('agents', {})

# Load roles
registry = load_role_registry()
role_names = registry.names()

# Check
missing = []
for agent_name, agent in agents_config.items():
    role = agent.get('role')
    if role and role not in role_names:
        missing.append((agent_name, role))

if missing:
    print("ERROR: Agents reference non-existent roles:")
    for agent, role in missing:
        print(f"  {agent} → {role}")
else:
    print("✓ All agents reference valid roles")
    print(f"  {len(agents_config)} agents, {len(role_names)} roles")
EOF
```

Expected output:
```
✓ All agents reference valid roles
  14 agents, 5 roles
```

---

## Section 4: Verify with Commands

### 4.1 List roles

```bash
agent-notes list roles
```

Expected output includes your new role:
```
Roles (5):
  orchestrator    Plans and delegates       (typical: opus)
  reasoner        Deep debugging            (typical: opus)
  scout           Fast discovery            (typical: haiku)
  specialist      Domain expert             (typical: sonnet)
  worker          Implements code           (typical: sonnet)
```

### 4.2 List agents

```bash
agent-notes list agents
```

Shows which agents use which roles:
```
Agents (15):
  lead          role: orchestrator
  debugger      role: reasoner
  explorer      role: scout
  specialist    role: specialist     ← your agent using new role
  coder         role: worker
  ...
```

### 4.3 Run wizard with new role

```bash
agent-notes install
```

**Step 1:** Select Claude Code

**Step 2:** Model selection should show all roles including the new one:
```
Orchestrator (Plans and delegates — typical: opus):
  1) [*] Claude Opus 4.7

Specialist (Domain expert for complex implementation details — typical: sonnet):
  1) [ ] Claude Haiku 4.5
  2) [*] Claude Sonnet 4
  3) [ ] Claude Opus 4.7

Worker (Implements code — typical: sonnet):
  ...
```

Notice `specialist` defaults to Sonnet (because `typical_class: sonnet`).

---

## Design Decisions: When to Add a New Role

### ✅ Add a new role if:

1. **Different model strategy needed** — The role needs a model class that no existing role targets.
   - Example: Add `analyst` with `typical_class: sonnet` if workers default to haiku but you want medium-reasoning analysis.

2. **Multiple agents need the same responsibility** — If 3+ agents do similar work, group them under one role for consistency.
   - Example: `lead`, `tech-lead`, `architect` → all could be role `orchestrator`

3. **Clear business meaning** — The role maps to a real job title or responsibility.
   - Good: `orchestrator`, `specialist`, `researcher`
   - Avoid: `tier-2`, `fast-model`, `expert-v2`

### ❌ Don't add a new role if:

1. **Per-agent override needed** — If one agent needs a different model, use state.json hand-edits or Phase 10's `set role` command with CLI-specific targeting.
   - Current: Can't set per-agent model in `agents.yaml`. Roles are the per-CLI grouping unit.

2. **Just a naming tweak** — Renaming "worker" to "coder" is fine but doesn't need a new role if the model strategy is the same.

3. **Capability-based filtering** — Roles are **NOT** for "vision-capable" vs "non-vision". That's future work (Phase 12+).

---

## Common Pitfalls

### Pitfall 1: Role created but agents don't reference it

**Problem:** You create `specialist.yaml` but no agent has `role: specialist`.

**Symptom:** Role appears in `agent-notes list roles` but never shows in wizard step 2.

**Solution:** Update `agents.yaml` to assign agents to the role. At least one agent must have `role: specialist`.

### Pitfall 2: `typical_class` doesn't match any model

**Problem:** You set `typical_class: ultrafast` but no models have `class: ultrafast`.

**Symptom:** Wizard doesn't default-check any model for this role.

**Solution:** Use existing classes: `opus`, `sonnet`, `haiku`, `flash`. To use a new class, also add models with that class (see `docs/ADD_MODEL.md`).

### Pitfall 3: Circular or conflicting role assignments

**Problem:** You move all agents from "worker" to "specialist", but build expects some agents in "worker".

**Symptom:** Build doesn't fail (roles are just declarations), but UI/docs mention "worker" and it has no agents.

**Solution:** Decide on your role taxonomy upfront. If removing "worker", either:
- Delete `worker.yaml`, OR
- Keep it but leave at least one agent assigned to it (for docs/UI consistency)

### Pitfall 4: YAML field typos

**Problem:** You write `typical-class` (hyphen) instead of `typical_class` (underscore).

**Symptom:** Loader crashes with `ValueError: Missing field 'typical_class'`.

**Solution:** Required fields (double-check):
```
name, label, description, typical_class
```

Optional fields:
```
color
```

### Pitfall 5: Role name conflicts with other systems

**Problem:** You create `role: system` or `role: default`, conflicting with Python keywords or Ansible conventions.

**Symptom:** No immediate error, but confusing for users and maintainers.

**Solution:** Use specific, business-meaningful names:
- Good: `orchestrator`, `specialist`, `researcher`, `explorer`
- Avoid: `default`, `system`, `main`, `admin` (too generic)

---

## Checklist

- [ ] Created `agent_notes/data/roles/specialist.yaml`
- [ ] All required fields present: `name`, `label`, `description`, `typical_class`
- [ ] `typical_class` matches a value used by existing models (e.g., `opus`, `sonnet`, `haiku`)
- [ ] `name` is lowercase, no spaces
- [ ] Assigned at least one agent to the role in `agents.yaml` (via `role: specialist`)
- [ ] Ran `agent-notes list roles` and saw the new role
- [ ] Ran `agent-notes list agents` and saw agents using the new role
- [ ] Ran `agent-notes install` and wizard step 2 shows the new role with model picker
- [ ] (Optional) Updated CLI_CAPABILITIES.md or internal docs with role description

---

## Next Steps

- **Test the full installation** with the new role:
  ```bash
  agent-notes install
  # Step 1: Select Claude Code
  # Step 2: Confirm new role appears and defaults correctly
  # Step 3: Pick Global
  # Step 4: Pick Symlink (recommended for testing)
  # Confirm and proceed
  ```

- **Inspect generated agents** to verify the role→model mapping:
  ```bash
  head -n 5 ~/.claude/agents/specialist.md
  # Should show:  model: claude-sonnet-4
  ```

- **Phase 10+: Use `set role` command** (when available):
  ```bash
  agent-notes set role specialist claude-opus-4-7 --cli claude
  # Updates state.json and regenerates affected agents
  ```

