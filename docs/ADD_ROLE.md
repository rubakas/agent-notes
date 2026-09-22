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
| `budget` | float or `null` | No | Max USD per 1M input tokens the automatic model-selection ladder will accept for this role. `null`/omitted = unbounded | `2.0` |
| `typical_effort` | string | No | Fallback reasoning effort (`low`, `medium`, `high`, ...) written to agent frontmatter when the agent doesn't declare its own `effort` | `"medium"` |
| `order` | int | No | Wizard display order (lower = earlier); roles with no `order:` sort last, then alphabetically | `3` |
| `color` | string | No | Display color in UI. No effect today | `"orange"`, `"blue"`, `"green"` |

**Key concepts:**

- **`name`** — Identifier used in:
  - `agents.yaml`: `lead: { role: specialist }`
  - Wizard step 2: `Specialist (...)` picker
  - Commands: `agent-notes set role specialist claude-sonnet-4`
  - state.json: `role_models: {specialist: "claude-sonnet-4"}`

- **`budget`** — the field that actually drives automatic model selection (`agent_notes/services/model_resolver.py::select_model_for_role`). It is not a hint: it is compared directly against a model's `price_in` (USD per 1M input tokens, from the catalog). The resolver walks a widening ladder of the catalog frontier (rated models, `coding_index` is not null, sorted capability-descending) and returns the first one priced at or under `role.budget` that the target backend can serve. When the backend declares a `preferred_family` (e.g. `opencode`'s `claude`), that family is tried first over the *whole* catalog and wins outright whenever any eligible model of that family exists — another family is only reachable when the preferred one has none. Widening past the non-deprecated rungs is legal but never silent: landing on a deprecated model emits a warning on stderr naming the model and the role. `null` (or omitting the field) means unbounded: any rated model is eligible regardless of price.

  Shipped values (`agent_notes/data/roles/*.yaml`):

  | Role | Budget |
  |------|--------|
  | `orchestrator` | `null` (unbounded) |
  | `reasoner` | `5.0` |
  | `worker` | `2.0` |
  | `scout` | `1.0` |

  `budget` only governs the *unpinned* fallback. A user can always override the automatic pick per role/backend with `agent-notes set role <role> <model> --cli <cli>` or a state pin, and a pin always wins over budget+rank selection.

- **`typical_effort`** — fallback reasoning-effort value (`low`, `medium`, `high`, ...) written to agent frontmatter when the agent doesn't declare its own `effort` in `agents.yaml`. An agent's explicit `effort` always wins.

- **`order`** — controls the role's position in the wizard's role list (sorted by `(order, name)`); roles with no `order:` default to `999` and sort last, then alphabetically. `agent-notes list roles` output is sorted alphabetically by name regardless of `order`.

- **`description`** — Shown in:
  - Wizard step 2: `Specialist (Deep expertise...)` — helps user understand what the role is for
  - `agent-notes list roles` output
  - Documentation (e.g., this guide)

- **`color`** (optional) — May be used by future UI enhancements. Current values: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan`. No effect today.

---

## Section 2: Step-by-Step — Create `agent_notes/data/roles/specialist.yaml`

### Step 2.1: Create the YAML descriptor

Create `agent_notes/data/roles/specialist.yaml`:

```yaml
name: specialist
label: Specialist
order: 5
description: Deep expertise in specific domains. Medium reasoning, high accuracy.
budget: 2.0   # max USD per 1M input tokens; null = unbounded
typical_effort: medium
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

- **`budget: 2.0`** — When the user accepts recommended models (or leaves this role unpinned), the wizard and the build both call `select_model_for_role`, which:
  - Filters models to those compatible with each CLI's `accepted_providers`
  - Walks the catalog frontier (rated, capability-descending)
  - Checks the box for the first model with `price_in <= 2.0`
  - User can uncheck and select a different (possibly pricier) model — `budget` only sets the default checkbox.

- **`typical_effort: medium`** — Preselects the wizard's effort picker for this role when `"medium"` is in the target provider's effort vocabulary; falls back to that provider's own `default_effort` otherwise.

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
print(f"Budget:         {role.budget}")
print(f"Typical effort: {role.typical_effort}")
print(f"Color:          {role.color}")
EOF
```

Expected output:
```
Name:           specialist
Label:          Specialist
Description:    Deep expertise in specific domains. Medium reasoning, high accuracy.
Budget:         2.0
Typical effort: medium
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

Expected output includes your new role (`list_roles()` sorts alphabetically by name and shows each role's `budget`):
```
Roles (5):
  orchestrator    Plans and delegates complex multi-step tasks. Low volume, high reasoning needed. (budget: unbounded)
  reasoner        Deep debugging and architecture analysis. Low volume, max reasoning needed. (budget: $5/M in)
  scout           Fast file discovery, pattern search. High volume, low reasoning. (budget: $1/M in)
  specialist      Deep expertise in specific domains. Medium reasoning, high accuracy. (budget: $2/M in)
  worker          Implements code, writes tests, does focused analysis. Medium volume. (budget: $2/M in)
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

**Step 2:** Model selection should show every role including the new one — except `orchestrator`, which the wizard always skips for the `claude` backend specifically ("Claude Code controls its own lead model via `/model`", `agent_notes/commands/wizard/__init__.py:174-178`):
```
Specialist (Deep expertise in specific domains. Medium reasoning, high accuracy.):
  1) [ ] claude-haiku-4-5
  2) [*] claude-sonnet-5
  3) [ ] claude-opus-5

Worker (Implements code, writes tests, does focused analysis...):
  ...
```

Notice `specialist` defaults to `claude-sonnet-5`, not a pricier Opus lineage: the default is whatever `select_model_for_role` returns for `budget: 2.0` — the first rated, backend-servable model in capability-descending order priced at or under $2.00/M input tokens. A user can still check a different box; `budget` only sets the default checkbox.

---

## Design Decisions: When to Add a New Role

### ✅ Add a new role if:

1. **Different model strategy needed** — The role needs a price ceiling that no existing role targets.
   - Example: Add `analyst` with `budget: 1.0` if `worker`'s `budget: 2.0` lets in pricier models than you want for medium-reasoning analysis.

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

### Pitfall 2: `budget` excludes every model

**Problem:** You set `budget: 0.5` but no rated model in the catalog is priced at or under $0.50/M input tokens for any backend the role needs.

**Symptom:** `select_model_for_role` returns `(None, None)`; `ModelResolver.resolve()` raises `ValueError: Agent '<agent>' has role='<role>' but no model could be resolved...` at build/install time — not a silent no-op.

**Solution:** Check `agent-notes list models` for `price_in` values and pick a budget at least one rated model clears, or set `budget: null` for unbounded.

### Pitfall 3: Circular or conflicting role assignments

**Problem:** You move all agents from "worker" to "specialist", but build expects some agents in "worker".

**Symptom:** Build doesn't fail (roles are just declarations), but UI/docs mention "worker" and it has no agents.

**Solution:** Decide on your role taxonomy upfront. If removing "worker", either:
- Delete `worker.yaml`, OR
- Keep it but leave at least one agent assigned to it (for docs/UI consistency)

### Pitfall 4: YAML field typos

**Problem:** You misspell a required field, e.g. `discription` instead of `description`.

**Symptom:** Loader crashes with `ValueError: Missing field '<field>' in <filename>`. A misspelled *optional* field (e.g. `budget-usd` instead of `budget`) is silently ignored instead — the role loads with that field at its default (`budget: null`, i.e. unbounded) and no error is raised.

**Solution:** Required fields (double-check):
```
name, label, description
```

Optional fields:
```
budget, color, typical_effort, order
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
- [ ] All required fields present: `name`, `label`, `description`
- [ ] `budget` set to a value at least one rated model in the catalog clears (or `null` for unbounded)
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
  # Should show:  model: claude-sonnet-5   (specialist's default pick for budget: 2.0)
  ```

- **Phase 10+: Use `set role` command** (when available):
  ```bash
  agent-notes set role specialist claude-opus-4-7 --cli claude
  # Updates state.json and regenerates affected agents
  ```

