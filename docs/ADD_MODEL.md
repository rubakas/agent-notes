# Adding a New AI Model

This guide shows how to add support for a new AI model (e.g., Kimi K2, GPT-5, Gemini 2.5) to agent-notes. Models are **purely declarative YAML files** — zero Python changes required.

---

## Section 1: Model Dataclass Fields

A **Model** is defined by these fields (all stored in YAML):

| Field | Type | Required | Purpose | Example |
|-------|------|----------|---------|---------|
| `id` | string | **Yes** | Unique identifier (lowercase, hyphens) | `"kimi-k2"` |
| `label` | string | **Yes** | Display name shown in UI | `"Moonshot Kimi K2"` |
| `family` | string | **Yes** | Brand/family (used for grouping) | `"kimi"`, `"openai"`, `"claude"` |
| `class` | string | **Yes** | Model tier for role defaults | `"opus"`, `"sonnet"`, `"haiku"` |
| `aliases` | dict[str, str] | **Yes** | Provider-specific model IDs | `{"openrouter": "moonshotai/kimi-k2"}` |
| `pricing` | dict[str, float] | No | Cost per token (optional, for reports) | `{"input": 0.05, "output": 0.15}` |
| `capabilities` | dict[str, bool] | No | Feature flags (optional, for filtering) | `{"vision": true, "long_context": true}` |

**Key concepts:**
- **`class`** hints which role typically uses this model (used by wizard to default-select a model for a role):
  - `"opus"` → high-reasoning models (orchestrator, reasoner roles)
  - `"sonnet"` → balanced models (worker role)
  - `"haiku"` → fast models (scout role)
  - `"flash"` → ultra-fast (new tier for fast models)
  - `"pro"` → specialty (future)
  
- **`aliases`** is critical: maps **provider names** (e.g., `"openrouter"`, `"openai"`, `"anthropic"`) to that provider's **model ID**. A model must have at least one alias for a CLI to use it.
  - Anthropic Direct: `anthropic: "claude-opus-4-7"`
  - AWS Bedrock: `bedrock: "anthropic.claude-opus-4-7-20260101-v1:0"` or ARN
  - Google Vertex: `vertex: "claude-opus-4-7@20260101"`
  - GitHub Copilot: `github-copilot: "github-copilot/claude-opus-4.7"`
  - OpenRouter: `openrouter: "anthropic/claude-opus-4.7"` or `"moonshotai/kimi-k2"`
  - OpenAI: `openai: "gpt-5"` or `"gpt-4o"`

- **Compatibility** is computed automatically: a model is compatible with a CLI iff the CLI's `accepted_providers` list has at least one key from the model's `aliases`. For example:
  - CLI: `accepted_providers: [anthropic, openrouter]`
  - Model with `aliases: {openrouter: "...", openai: "..."}` → **compatible** (openrouter matches)
  - Model with `aliases: {openai: "...", google: "..."}` → **incompatible** (no overlap)

---

## Section 2: Step-by-Step — Create `agent_notes/data/models/kimi-k2.yaml`

### Step 2.1: Create the YAML descriptor

Create `agent_notes/data/models/kimi-k2.yaml`:

```yaml
id: kimi-k2
label: Moonshot Kimi K2
family: kimi
class: opus
aliases:
  openrouter: moonshotai/kimi-k2
  moonshot:   moonshot/kimi-k2
pricing:
  input:  0.0015
  output: 0.002
  cache:  0.0003
capabilities:
  vision: true
  long_context: true
  tool_use: false
```

**Field explanations:**

- **`id: kimi-k2`** — Unique ID. Must be lowercase with hyphens (no spaces). Used in:
  - Wizard step 2 (model picker)
  - state.json (`role_models: {orchestrator: "kimi-k2"}`)
  - Commands: `agent-notes set role orchestrator kimi-k2`

- **`label: Moonshot Kimi K2`** — Shown in UI and docs. Human-readable.

- **`family: kimi`** — Brand identifier. Used for:
  - Grouping models by vendor in `list models` output
  - Future filtering ("show me all kimi models")

- **`class: opus`** — Model capability tier. Sets default role assignments in wizard:
  - Wizard shows this model as the `[*]` default for any role with `typical_class: opus`
  - Example: Role "orchestrator" has `typical_class: opus`, so Kimi K2 (with `class: opus`) is checked by default for that role

- **`aliases`** — Provider-to-model-id mapping. At install time, agent-notes:
  1. Reads CLI's `accepted_providers` (e.g., `[openrouter, moonshot]`)
  2. Looks for the **first** matching key in this model's aliases
  3. Resolves the alias value (e.g., `"moonshotai/kimi-k2"`)
  4. Writes that into the agent's frontmatter `model:` field

  Examples for common providers:
  ```yaml
  aliases:
    anthropic:      claude-opus-4-7                    # Direct Anthropic API
    bedrock:        anthropic.claude-opus-4-7-v1:0     # AWS Bedrock model ID
    vertex:         claude-opus-4-7@20250101           # Google Vertex location-prefixed
    github-copilot: github-copilot/claude-opus-4.7    # GitHub Copilot provider
    openai:         gpt-5                              # OpenAI direct model alias
    openrouter:     openai/gpt-5                       # OpenRouter vendor prefix
  ```

- **`pricing`** (optional) — Cost per million tokens. Used for:
  - Future cost estimation tools
  - Informational displays in `list models`
  - Keys can be: `input`, `output`, `cache` (per-provider pricing not yet supported)

- **`capabilities`** (optional) — Feature flags. Reserved for future filtering:
  - `vision: true/false` — Can process images
  - `long_context: true/false` — Has 100k+ token context
  - `tool_use: true/false` — Can invoke tools/functions
  - (More capabilities may be added as features require)

### Step 2.2: Verify YAML is valid

```bash
python3 -c "import yaml; yaml.safe_load(open('agent_notes/data/models/kimi-k2.yaml'))"
# Should produce no output (success).
```

### Step 2.3: Test registry loading

```bash
python3 << 'EOF'
from agent_notes.model_registry import load_model_registry

registry = load_model_registry()
model = registry.get("kimi-k2")
print(f"ID:       {model.id}")
print(f"Label:    {model.label}")
print(f"Class:    {model.model_class}")
print(f"Aliases:  {model.aliases}")
EOF
```

Expected output:
```
ID:       kimi-k2
Label:    Moonshot Kimi K2
Class:    opus
Aliases:  {'openrouter': 'moonshotai/kimi-k2', 'moonshot': 'moonshot/kimi-k2'}
```

---

## Section 3: How Model Selection Flows

Understanding the resolution chain helps verify your model works end-to-end.

### Install-time flow

```
1. User runs:  agent-notes install

2. Wizard step 1: User selects CLIs
   → Loaded from data/cli/*.yaml

3. Wizard step 2: Model selection per role per CLI
   → For each (role, CLI) pair:
     a. Load role from registry (e.g., "orchestrator" with typical_class="opus")
     b. Get CLI's accepted_providers (e.g., ["openrouter", "anthropic"])
     c. Filter models: keep those compatible with CLI
        (model has alias for ≥1 provider in CLI's list)
     d. Default-check models whose class matches role's typical_class
     e. Show picker; user selects one
     f. Write choice to state (e.g., {"orchestrator": "kimi-k2"})

4. Build time: generate agents
   → For each agent in agents.yaml:
     a. Get agent's role (e.g., "orchestrator")
     b. Look up state[scope].clis[cli].role_models["orchestrator"]
        → Get model_id (e.g., "kimi-k2")
     c. Load model from registry
     d. Call model.resolve_for_providers(cli.accepted_providers)
        → Returns (provider, resolved_id)
        → Example: ("openrouter", "moonshotai/kimi-k2")
     e. Load frontmatter template
     f. Render frontmatter with model_id = resolved_id
     g. Write agent file with frontmatter + prompt
```

### Example: Install Kimi K2 for OpenCode

```bash
# Step 1: User selects OpenCode
# Step 2: For "orchestrator" role:
#   - Wizard shows: Claude Opus 4.7 [*], Kimi K2 [ ], GPT-5 [ ]
#   - Kimi K2 is selectable because:
#     * OpenCode.accepted_providers = ["github-copilot", "openrouter"]
#     * Kimi K2.aliases = {"openrouter": "moonshotai/kimi-k2", ...}
#     * "openrouter" is in both lists → compatible
# Step 3: User selects Kimi K2 → state saves {"orchestrator": "kimi-k2"}
# Step 4: Build generates agents:
#   - For "lead" agent (role: orchestrator):
#     * Resolve: kimi-k2 for OpenCode (accepted_providers = ["github-copilot", "openrouter"])
#     * First matching provider in accepted_providers: "openrouter"
#     * model_id = aliases["openrouter"] = "moonshotai/kimi-k2"
#     * Frontmatter: model: moonshotai/kimi-k2
```

---

## Section 4: Verify with Commands

### 4.1 List models

```bash
agent-notes list models
```

Expected output includes your new model:
```
Models (5):
  claude-haiku-4-5       Claude Haiku 4.5        [haiku]   compatible: claude, opencode, copilot
  claude-opus-4-7        Claude Opus 4.7         [opus]    compatible: claude, opencode, copilot
  claude-sonnet-4        Claude Sonnet 4         [sonnet]  compatible: claude, opencode, copilot
  kimi-k2                Moonshot Kimi K2        [opus]    compatible: opencode
  ...
```

Notice `compatible: opencode` — this was auto-computed from:
- OpenCode.accepted_providers = ["github-copilot", "openrouter"]
- Kimi K2.aliases keys = ["openrouter", "moonshot"]
- Intersection = ["openrouter"] → compatible!

### 4.2 Run wizard with new model

```bash
agent-notes install
```

**Step 1:** Select OpenCode

**Step 2:** For "orchestrator" role, you should see:
```
Orchestrator (plans, delegates — typical: opus):
  1) [ ] Claude Opus 4.7        (via anthropic)
  2) [ ] Kimi K2                (via openrouter)
  3) [*] Claude Sonnet 4        (via github-copilot)  ← default
```

Wait, why is Sonnet defaulted, not Opus? Because of how the wizard picks defaults:
- Role "orchestrator" has `typical_class: opus`
- Available models with `class: opus`:
  - Claude Opus 4.7 (anthropic) ← matches "orchestrator" typical_class
  - Kimi K2 (openrouter) ← also matches
- Wizard picks one. The exact behavior depends on the wizard's default selection logic.

### 4.3 Set role command (Phase 10)

Once Phase 10 is complete, you can change model assignments post-install:

```bash
agent-notes set role orchestrator kimi-k2 --cli opencode
# Output: Updated opencode: orchestrator → kimi-k2
# Then regenerates affected agents
```

---

## Section 5: Make Model Available for Specific CLIs Only

By default, a model is available to **all CLIs** that have a matching provider in their `accepted_providers`.

**Example:** Kimi K2 has aliases for `["openrouter", "moonshot"]`. If only OpenCode accepts "openrouter", Kimi is available only for OpenCode.

### To restrict further

There's no per-CLI filtering in the model YAML itself (no `supported_clis` field yet). Restriction happens at the CLI level:

**Option 1: CLI configuration** (current method)
- Kimi only available if you want it in OpenCode?
- OpenCode has `accepted_providers: ["github-copilot", "openrouter"]`
- If Claude has `accepted_providers: ["anthropic", "bedrock", "vertex"]` (no openrouter), Kimi won't be offered for Claude
- **So control availability by controlling each CLI's `accepted_providers` list**

**Option 2: Future — capability matching**
- Future versions may support: Model declares `requires_providers: ["openrouter"]`, CLI declares `provides_providers: ["openrouter"]`
- For now, this is in `CLI_CAPABILITIES.md` for documentation only, not enforced in code

---

## Common Pitfalls

### Pitfall 1: Model has no aliases for any installed CLI

**Problem:** You create a model with only Bedrock aliases, but your CLIs only accept "anthropic".

**Symptom:** `agent-notes install` shows the model nowhere in step 2.

**Solution:** Add aliases that match at least one CLI's `accepted_providers`. Check existing CLIs:
```bash
python3 << 'EOF'
from agent_notes.cli_backend import load_registry

registry = load_registry()
for cli in registry.all():
    print(f"{cli.name}: {cli.accepted_providers}")
EOF
```

Output:
```
claude: ('anthropic', 'bedrock', 'vertex')
copilot: ('github-copilot',)
opencode: ('github-copilot', 'openrouter')
```

So for a model to appear in the wizard for OpenCode, it needs an alias for `github-copilot` or `openrouter`.

### Pitfall 2: Wrong alias format for provider

**Problem:** You set `openai: gpt-5` but the actual provider expects `openai-v1: ...` or has different format.

**Symptom:** Agent file is generated with `model: gpt-5`, but the CLI doesn't recognize it.

**Solution:** Check the provider's docs or existing models in the registry:
```bash
python3 << 'EOF'
from agent_notes.model_registry import load_model_registry

registry = load_model_registry()
for model in registry.all():
    if "openai" in model.aliases:
        print(f"{model.id}: openai → {model.aliases['openai']}")
EOF
```

If no models exist for that provider yet, check CLI's official docs for the model ID format.

### Pitfall 3: YAML field typos

**Problem:** You write `aliases:` but the loader expects `alias:` (singular).

**Symptom:** Loader crashes with `ValueError: Missing field 'aliases'`.

**Solution:** Required fields are:
```
id, label, family, class, aliases
```

Optional fields:
```
pricing, capabilities
```

### Pitfall 4: `class` doesn't match role's `typical_class`

**Problem:** You set `class: flash` (new ultra-fast tier) but roles only have `typical_class: [opus, sonnet, haiku]`.

**Symptom:** Model doesn't get default-selected in wizard. Not wrong, just doesn't auto-default.

**Solution:** Use existing classes for now (`opus`, `sonnet`, `haiku`). Or:
1. Add new role with `typical_class: flash` (see `docs/ADD_ROLE.md`)
2. Or accept that the model won't auto-default and users manually select it

### Pitfall 5: `aliases` values are hardcoded but change

**Problem:** You hardcode `anthropic: "claude-opus-4-7"` but Anthropic changes the model ID format in a new release.

**Symptom:** Installation works today but breaks when Anthropic updates.

**Solution:** No automated solution yet. This is why `docs/CLI_CAPABILITIES.md` exists — to document provider-specific formats. If the format changes:
1. Update the model YAML
2. Re-run `agent-notes regenerate` to rebuild agents with new aliases

---

## Checklist

- [ ] Created `agent_notes/data/models/kimi-k2.yaml`
- [ ] All required fields present: `id`, `label`, `family`, `class`, `aliases`
- [ ] `class` matches one of: `opus`, `sonnet`, `haiku`, `flash` (or a new class with roles to match)
- [ ] `aliases` has at least one provider matching a CLI's `accepted_providers`
  - Check with: `agent-notes list clis` or inspect `data/cli/*.yaml`
- [ ] `id` is lowercase with hyphens, no spaces
- [ ] Ran `agent-notes list models` and saw the new model
- [ ] Ran `agent-notes install` and the model appears in step 2 (for compatible CLIs)
- [ ] Wizard step 2 shows the model and allows selection (if compatible with selected CLI)

---

## Next Steps

- **Add a new role** if you want this model to default for a new role type: see `docs/ADD_ROLE.md`.
- **Update CLI_CAPABILITIES.md** with details about the model's provider if relevant (e.g., "Kimi K2 available via OpenRouter at...").
- **Set role** (Phase 10+): `agent-notes set role orchestrator kimi-k2 --cli opencode` to test post-install changes.

