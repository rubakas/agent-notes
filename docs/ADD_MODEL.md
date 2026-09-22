# Adding a New AI Model

This guide shows how to add a new AI model to agent-notes' live catalog. Models are **not** individual YAML files per model — they are entries in a shared seed file (`agent_notes/data/catalog/seed.json`) plus glob-based rules (`agent_notes/data/catalog/rules.yaml`) that a loader composes into `Model` objects at runtime (`agent_notes.registries.catalog_loader.load_catalog`). Zero Python changes required, but the mechanics differ from "drop a YAML file" — see Section 2.

---

## Section 1: Model Dataclass Fields

A **Model** (`agent_notes/domain/model.py`) has these fields. Some are supplied directly by a `seed.json` provider entry; the rest are DERIVED at load time by `catalog_loader.load_catalog` from `rules.yaml` glob rules — they are never written per-model by an author.

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `id` | string | Seed `id`, normalized (anthropic: unchanged; openai: dots → dashes, e.g. `gpt-5.4` → `gpt-5-4`) | Unique identifier |
| `label` | string | Seed `display_name` (anthropic) or derived from `id` (openai, e.g. `gpt-5.4-mini` → `GPT-5.4 Mini`) | Display name |
| `family` | string | **DERIVED** — first `rules.yaml` `families` glob matching `id` | Brand grouping, e.g. `claude`, `gpt` |
| `model_class` (`class`) | string | **DERIVED** — first `rules.yaml` `classes` glob matching `id` | Tier tag. For the *unpinned* budget+rank fallback on backends with `use_model_class: true` (currently only `claude`), this string — not the resolved alias — is written into the agent's `model:` frontmatter field |
| `aliases` | dict[str, str] | **DERIVED** — a single entry keyed by the seed provider block the model came from: `alias_transforms[provider].format(id=id, seed_id=seed_id)`, overridable per-model via `alias_overrides[provider][id]` | Provider-specific model id string |
| `capabilities` | dict[str, bool] | **DERIVED** — `rules.yaml capabilities.default` merged with `capabilities.overrides[id]` | Feature flags (vision, long_context, tool_use, effort_support) |
| `deprecated` | bool | **DERIVED** — `id in rules.yaml deprecated` | Soft preference in the selection ladder (see `model_resolver.py`); does not filter a model out entirely |
| `rank` | int | Seed `rank` | Author-supplied ordering *within* a provider's block; NOT the global selection order — see below |
| `coding_index` | float or `null` | Seed `coding_index` | Benchmark score. Gates automatic selection: a model with `coding_index: null` is never auto-selected |
| `intelligence_index` | float or `null` | Seed `intelligence_index` | Benchmark score, informational |
| `price_in` | float or `null` | Seed `price_in`, overridable per-model via `rules.yaml price_overrides[id].price_in` | USD per 1M input tokens; compared directly against `role.budget` |
| `price_out` | float or `null` | Seed `price_out`, overridable per-model via `rules.yaml price_overrides[id].price_out` | USD per 1M output tokens |
| `context_length` | int or `null` | Seed `context_length` | Informational |
| `created_at` | string or `null` | Seed `created_at` | Informational |

**Key concepts:**

- **A model's `aliases` dict always has exactly one entry**, keyed by the provider block it was loaded from in `seed.json` (`agent_notes/registries/catalog_loader.py:205`). There is no way to give one model multiple provider aliases (e.g. both `anthropic` and `bedrock`) today — see the Pitfalls section.

- **`class` does not drive selection.** It is derived from `rules.yaml`'s `classes` globs and is rendered into frontmatter only on backends with `use_model_class: true` (currently `claude` alone). Automatic model selection is driven entirely by `role.budget` + `coding_index` — see Section 3 and `docs/ADD_ROLE.md`.

- **Compatibility** is computed automatically: a model is compatible with a CLI iff the CLI's `accepted_providers` list contains the model's single alias-provider key. For example:
  - CLI: `accepted_providers: [anthropic, bedrock, vertex]`
  - Model loaded from the seed's `anthropic` block → alias key `anthropic` → **compatible**
  - Model loaded from the seed's `openai` block → alias key `openai` → **incompatible** with a CLI that only accepts `anthropic`/`bedrock`/`vertex`

---

## Section 2: Step-by-Step — Add an entry to `agent_notes/data/catalog/seed.json`

There is no `agent_notes/data/models/` directory and no per-model YAML file. The live loader (`catalog_loader.load_catalog`, wired at `agent_notes/registries/model_registry.py:104-114`) reads exactly two files: `agent_notes/data/catalog/seed.json` (per-provider model data) and `agent_notes/data/catalog/rules.yaml` (glob rules that derive `family`/`class`/`aliases`/`capabilities`/`deprecated`). A file dropped at the old `data/models/<id>.yaml` path is never read by `load_model_registry()` in production — see "Legacy per-file loader" below for the one place that path still applies.

### Step 2.1: Add a provider entry to `seed.json`

`seed.json` today has two provider blocks: `anthropic` and `openai` (`agent_notes/data/catalog/seed.json`). Adding a model already on one of those providers means appending an entry to its array:

```json
{
  "id": "claude-opus-5-1",
  "display_name": "Claude Opus 5.1",
  "coding_index": 79.2,
  "intelligence_index": 51.0,
  "price_in": 5.0,
  "price_out": 25.0,
  "context_length": 1000000,
  "created_at": "2026-10-01",
  "rank": 1
}
```

**Field explanations:**

- **`id`** — the seed id. For `anthropic` it becomes the model's registry `id` unchanged. For `openai` it is normalized (dots → dashes) before becoming the registry `id`, e.g. `"gpt-5.5"` → `gpt-5-5`.
- **`display_name`** (anthropic only) — becomes `Model.label` verbatim. openai has no `display_name`; its label is derived from `id` by `_derive_openai_label` (`"gpt-5.4-mini"` → `"GPT-5.4 Mini"`).
- **`coding_index` / `intelligence_index`** — benchmark scores. `coding_index: null` (or omitted) makes the model permanently ineligible for automatic selection (`_eligible()` in `model_resolver.py` requires a non-null score) — it can still be reached by an explicit pin.
- **`price_in` / `price_out`** — USD per 1M tokens. `price_in` is what `role.budget` is compared against.
- **`price_overrides`** — a top-level block in `agent_notes/data/catalog/rules.yaml`, indexed by normalized registry id, that pins `price_in`/`price_out` on top of whatever the seed reports (`catalog_loader.py::_apply_price_overrides`). Two reasons to reach for it instead of editing `seed.json` directly: `seed.json` is machine-refreshed from OpenRouter by `models refresh` and would silently reintroduce a wrong price on the next refresh, and `~/.cache/agent-notes/catalog.json` shadows the bundled `seed.json` at runtime (`catalog_loader.py:173-178`) — editing `seed.json` alone can appear to do nothing on a machine that already has a cache, since `rules.yaml` (and `price_overrides` with it) is read fresh every time and always wins. The live entry:
  ```yaml
  price_overrides:
    gpt-5-6-sol:
      price_in: 4.0
      price_out: 20.0
  ```
  pins GPT-5.6 Sol to OpenAI's published $4.00/$20.00 rate after the OpenRouter-sourced seed reported $2.00/$10.00.
- **`rank`** — 1-based position within *this provider's* array. It does not by itself decide selection order across the whole catalog: `ModelRegistry` sorts every model globally by `coding_index` descending (`_frontier_key`), unrated models last. Keep `rank` consistent with `coding_index` ordering within a provider to avoid a confusing catalog.
- **`created_at` / `context_length`** — informational, not consulted by selection logic.

A brand-new **family** (not `claude-*` or `gpt-*`) needs two more things before it resolves:

1. A new top-level key under `"providers"` in `seed.json`, e.g. `"kimi": [...]`.
2. A matching glob in `agent_notes/data/catalog/rules.yaml`'s `families:` and `classes:` lists — otherwise `catalog_loader._apply_family`/`_apply_class` raise `ValueError: No family rule matched '<id>'`. An `alias_transforms:` entry for the new provider key is optional (defaults to the id unchanged, `"{id}"`, if omitted).

### Step 2.2: Verify the files parse

```bash
python3 -c "import json; json.load(open('agent_notes/data/catalog/seed.json'))"
python3 -c "import yaml; yaml.safe_load(open('agent_notes/data/catalog/rules.yaml'))"
# Both should produce no output (success).
```

### Step 2.3: Test registry loading

```bash
python3 << 'EOF'
from agent_notes.registries.model_registry import load_model_registry

registry = load_model_registry()
model = registry.get("claude-opus-5-1")
print(f"ID:       {model.id}")
print(f"Label:    {model.label}")
print(f"Family:   {model.family}")
print(f"Class:    {model.model_class}")
print(f"Aliases:  {model.aliases}")
print(f"Coding index: {model.coding_index}")
print(f"Price in: {model.price_in}")
EOF
```

Expected output (family/class are DERIVED from `rules.yaml`'s globs, not authored above):
```
ID:       claude-opus-5-1
Label:    Claude Opus 5.1
Family:   claude
Class:    opus
Aliases:  {'anthropic': 'claude-opus-5-1'}
Coding index: 79.2
Price in: 5.0
```

### Legacy per-file loader (tests only)

`agent_notes/registries/model_registry.py::_load_from_yaml_dir` still loads a directory of per-model YAML files (`id`, `label`, `family`, `class`, `aliases` required, mirroring the old schema) — but only when `load_model_registry(models_dir=...)` is called with an explicit directory. Production code never passes `models_dir`, so this path is exercised only by tests that build fixture registries on disk (e.g. `tests/unit/registries/test_registries.py`). Do not rely on it for real models.

---

## Section 3: How Model Selection Flows

Understanding the resolution chain helps verify your model works end-to-end.

### Install-time flow

```
1. User runs:  agent-notes install

2. Wizard step 1: User selects CLIs
   → Loaded from data/cli/*.yaml

3. Wizard step 2: Model selection per role per CLI
   → For each (role, CLI) pair, the wizard's default checkbox calls the SAME
     function the build uses — select_model_for_role(models, role, backend)
     (agent_notes/services/model_resolver.py) — so the two can never disagree:
     a. Load role from registry (e.g., "orchestrator" with budget=null)
     b. Filter to models compatible with the CLI's accepted_providers
        (model's single alias-provider key is in that list)
     c. Walk a widening ladder over the catalog frontier (coding_index
        descending): if the backend declares preferred_family, that family
        is tried first over the whole catalog and wins outright whenever it
        has any eligible model — only then does the ladder fall back to any
        family, and only then to deprecated models (with a stderr warning).
        Default-check the first rated model priced at or under role.budget
     d. Show picker; user can accept the default or pick another
     e. Write choice to state (e.g., {"orchestrator": "claude-opus-5-1"})

4. Build time: generate agents
   → For each agent in agents.yaml:
     a. Get agent's role (e.g., "orchestrator")
     b. Look up state[scope].clis[cli].role_models["orchestrator"]
        → Get model_id (e.g., "claude-opus-5-1")
     c. Load model from registry
     d. Call model.resolve_for_providers(cli.accepted_providers)
        → Returns (provider, resolved_id)
        → Example: ("anthropic", "claude-opus-5-1")
     e. Load frontmatter template
     f. Render frontmatter with model_id = resolved_id
     g. Write agent file with frontmatter + prompt
```

### Example: automatic selection for `orchestrator`

`orchestrator`'s `budget` is `null` (unbounded), so the resolver walks the frontier and picks whichever rated model has the highest `coding_index` that the backend can serve — today that is `claude-fable-5-1` (`coding_index: 81.6`, rank 1 in the `anthropic` seed block), not the model with `class: opus`. `class` is not consulted at all in this decision.

```
# For a Claude backend (accepted_providers includes "anthropic"):
#   - claude-fable-5-1 is rated and unbounded budget accepts any price
#     → automatic pick for "orchestrator", no explicit pin needed
# For a backend whose accepted_providers has no overlap with claude-fable-5-1's
# single alias ("anthropic"), the resolver keeps walking the frontier to the
# next rated, servable model.
```

### Known limitation: one shared `dist/` across scopes

`dist/` is a single shared render target: global and local installs (and named profiles) all re-render the same `dist/<cli>/agents/` files, and the last build wins. Installed symlinks point into `dist/`, so divergent per-scope pins cannot coexist — a healthy `agent-notes install` in one scope re-renders `dist/` from that scope's pins and can silently flip the agents another scope's symlinks serve. Workaround: keep role/model pins consistent across scopes, or re-run `agent-notes install` (or `agent-notes build`) in the affected scope to re-render its pins.

---

## Section 4: Verify with Commands

### 4.1 List models

```bash
agent-notes list models
```

`list_models()` groups by provider (each provider's `rank` is only meaningful within its own block) and renders every model through the shared `model_columns` helper — the same columns the wizard and `config role-model` use:

```
Models (N):

  anthropic (M):
    rank  model                          int  coding    $/M in
       1  claude-fable-5-1              53.4    81.6      10.00
       2  claude-opus-5                 50.7    78.0       5.00
       3  claude-fable-5                49.7    76.5      10.00
       ...
       X  claude-opus-5-1               51.0    79.2       5.00

  openai (K):
    rank  model                          int  coding    $/M in
       1  gpt-5-6-sol                    47.1    77.4       2.00
       2  gpt-6-astra                    52.8    76.9      10.00
       ...
```

A model with `coding_index: null` prints `—` in the `coding` column and is never auto-selected.

### 4.2 Run wizard with new model

```bash
agent-notes install
```

**Step 1:** Select OpenCode (`accepted_providers: [anthropic, openai]`, `preferred_family: claude`)

**Step 2:** For "orchestrator" role (`budget: null`), the wizard's radio list is a flat list of compatible models rendered through `model_columns` (columns: model id, `int`, `coding`, `$/M in` — `class` is not shown). The pre-checked default is whichever rated model the backend can serve with the highest `coding_index` — today `claude-fable-5-1`:
```
CLI           OpenCode
Role          Orchestrator
Description   Plans and delegates complex multi-step tasks...
   model                          int  coding    $/M in
  1) [*] claude-fable-5-1        53.4    81.6      10.00
  2) [ ] claude-opus-5-1         51.0    79.2       5.00
  3) [ ] claude-opus-5           50.7    78.0       5.00
  ...
```

`class` is not part of this decision at all — `claude-fable-5-1`'s `class` is `fable`, not `opus`, and it is still the default, and is not displayed in the picker. `worker` (`budget: 2.0`) or `scout` (`budget: 1.0`) would instead default to the highest-`coding_index` rated model priced at or under their respective ceilings — for `worker` on a `claude`-family-preferring backend, that is `claude-sonnet-5` (`coding_index: 71.5`, `price_in: 2.0`), since every pricier Sonnet/Opus lineage is either deprecated or over budget.

Note: the wizard skips the `orchestrator` role entirely for the `claude` backend specifically — "Claude Code controls its own lead model via `/model`" (`agent_notes/commands/wizard/__init__.py:174-178`) — so this role/backend pairing only appears for backends other than `claude`.

### 4.3 Set role command

You can change model assignments post-install:

```bash
agent-notes set role orchestrator claude-opus-5-1 --cli opencode
# Updates state.json and regenerates affected agents
```

---

## Section 5: Make Model Available for Specific CLIs Only

A model is available to a CLI iff its single alias-provider key is in that CLI's `accepted_providers`.

**Example:** a model loaded from the seed's `openai` block has `aliases: {"openai": "..."}`. `codex` (`accepted_providers: [openai]`) and `opencode` (`accepted_providers: [anthropic, openai]`) can serve it; `claude` (`accepted_providers: [anthropic, bedrock, vertex]`) cannot.

### To restrict further

There's no per-CLI filtering in the seed data itself (no `supported_clis` field). Availability is controlled entirely by each CLI's `accepted_providers` list in `agent_notes/data/cli/*.yaml` — a model is offered to a CLI iff there's overlap, nothing more granular exists today.

---

## Common Pitfalls

### Pitfall 1: Model has no aliases for any installed CLI

**Problem:** You create a model with only Bedrock aliases, but your CLIs only accept "anthropic".

**Symptom:** `agent-notes install` shows the model nowhere in step 2.

**Solution:** Add the model under a provider block whose key matches at least one CLI's `accepted_providers`. Check existing CLIs:
```bash
python3 << 'EOF'
from agent_notes.registries.cli_registry import load_registry

registry = load_registry()
for cli in registry.all():
    print(f"{cli.name}: {cli.accepted_providers}")
EOF
```

Output:
```
claude:   ('anthropic', 'bedrock', 'vertex')
codex:    ('openai',)
copilot:  ('github-copilot',)
opencode: ('anthropic', 'openai')
```

So a model only reaches `codex` if it came from the seed's `openai` block (or a user override adds an `openai` alias); `copilot` has no models today, since neither seed provider block is `github-copilot`.

### Pitfall 2: Wrong alias format for a provider

**Problem:** The derived alias (via `alias_transforms`) doesn't match what the provider actually expects — e.g. anthropic needs a dated id (`claude-sonnet-4-20250514`) but the transform emits the bare `id`.

**Symptom:** Agent file is generated with a `model:` value the provider's API rejects.

**Solution:** Add a per-model override in `agent_notes/data/catalog/rules.yaml`'s `alias_overrides:` block (see the existing `claude-sonnet-4` entry), or in `~/.config/agent-notes/models.yaml` for a local-only override — both are keyed `provider -> normalized_id -> alias_string`.

### Pitfall 3: New model's id doesn't match any `family`/`class` glob

**Problem:** You add a `seed.json` entry whose `id` doesn't match any pattern in `rules.yaml`'s `families:` or `classes:` lists (e.g. a brand-new family with no existing glob).

**Symptom:** `catalog_loader._apply_family`/`_apply_class` raise `ValueError: No family rule matched '<id>'` (or the `classes` equivalent) — the whole catalog fails to load, not just the new model.

**Solution:** Add a matching glob to `rules.yaml`'s `families:`/`classes:` lists (or a narrower one ahead of the existing catch-alls, since first match wins), or add an `alias_overrides`/`id` that matches an existing pattern.

### Pitfall 4: `class` does not affect automatic selection

**Problem:** You expect a new `class: flash` model to become the default pick for a role because you assume `class` is compared against something on the role.

**Symptom:** The model is or isn't auto-selected based purely on `coding_index` + `role.budget` — `class` never enters the decision. `class` affects only what gets written into the agent's `model:` frontmatter field, and only for the *unpinned* budget+rank fallback on backends with `use_model_class: true` (currently `claude` alone): there, `model:` is rendered as the bare class string (e.g. `sonnet`) instead of the resolved alias. Every other backend, and every explicit pin (state or `set role`) regardless of backend, always renders the exact alias string. The wizard's model picker itself never displays `class` at all (see Section 4.2).

**Solution:** To change a role's default pick, adjust `role.budget` (see `docs/ADD_ROLE.md`) — not the model's `class`.

### Pitfall 5: Alias values are hardcoded but change

**Problem:** A provider's model-id format changes (Anthropic ships a new dated id, for example), but the `alias_transforms`/`alias_overrides` entry in `rules.yaml` still emits the old form.

**Symptom:** Installation works today but produces a rejected `model:` value once the provider retires the old id.

**Solution:** No automated solution yet. If the format changes:
1. Update the `alias_overrides` (or `alias_transforms`) entry in `rules.yaml`
2. Re-run `agent-notes regenerate` to rebuild agents with the corrected alias

### Pitfall 6: Bare provider aliases that equal a class name

**Problem:** An alias resolves to a bare class-like string (e.g. `sonnet`) instead of a version-pinned id (`claude-sonnet-4-6`). With the live loader, `alias_transforms`/`alias_overrides` are the only place this could be introduced.

**Symptom (silent drift):** Anthropic resolves bare aliases like `sonnet` server-side to whatever they currently consider their newest Sonnet model. When Anthropic ships a new Sonnet release, your pinned agent silently starts running a different model — no error, no changelog entry in this repo, just different behavior.

**Symptom (test fragility):** A bare alias that happens to equal its `class` value makes it easy to write a resolver test that checks against `model.model_class` instead of the actual resolved alias — the two strings match by coincidence, and the test stays green even if the resolution logic is broken. This bit `test_model_resolver_characterization.py` in the past: fixing a bare `sonnet` alias to `claude-sonnet-4-6` immediately surfaced a latent bug in the "expected value" computation of three tests, because the coincidence had been hiding it.

**Solution:** Alias values must always be version-pinned ids, never bare class names. `tests/unit/registries/test_registries.py::test_model_aliases_are_exact_version_strings_not_class_names` enforces `alias != class` for every model/provider pair — a bare alias will fail the suite. Do not introduce a bare alias via `alias_transforms` or `alias_overrides`.

---

## Catalog refresh

`agent_notes/data/catalog/seed.json` carries a `fetched_at` timestamp and is refreshed by a separate `models refresh` workflow driven by `rules.yaml`'s `filter:` block (per-provider `allow`/`exclude` globs). Refreshing the catalog, deprecating models, and cost tracking are live today (`rank`, `coding_index`, `price_in`/`price_out`, `deprecated` are all read by the resolver and cost subsystem) — this is no longer future work. Do not add a per-model YAML file expecting it to participate in a refresh; only `seed.json` and `rules.yaml` are refreshed.

---

## Section 6: Providers registry (effort vocabularies)

`agent_notes/data/providers/*.yaml` declares, per provider, the reasoning-effort values it accepts and its own default:

```yaml
name: anthropic
efforts: [low, medium, high, xhigh, max]
default_effort: high
```

**Hard rule: no cross-provider mapping or translation, anywhere.** Each provider's effort vocabulary is independent — `anthropic`'s `xhigh` is not translated to `openai`'s `xhigh` or anything else; they're just two providers that both happen to define a value with that name. If a resolved effort value isn't in the target provider's `efforts` list, the fallback is that provider's own `default_effort` — never another provider's value, never a translated/mapped equivalent.

Providers with no YAML file here (`github-copilot`, `openrouter`, `google`, `moonshot` as of this writing) deliberately have no effort support: `agent_notes/registries/provider_registry.py`'s `.get()` raises `KeyError` for them, and the rendering seam (`rendering.py::_resolve_effort`) treats that as "emit nothing" rather than guessing a default. Adding effort support for a new provider means adding its YAML file with its own accurate `efforts`/`default_effort` — not reusing another provider's list.

**Per-model gate: `effort_support`.** Independent of provider vocabulary, a model can be marked as accepting no effort setting at all via the `effort_support` capability under `rules.yaml`'s `capabilities:` block:

```yaml
capabilities:
  default:
    effort_support: true
  overrides:
    claude-haiku-4-5:
      effort_support: false
```

Default is `true` (`capabilities.default.effort_support`). Setting it `false` under `capabilities.overrides[id]` makes `rendering.py`'s `_resolve_effort` omit the `effort` field entirely for that model (`rendering.py:265-266`) — this gate is checked before any provider-vocabulary validation runs. The live case is `claude-haiku-4-5`: it is absent from the supported-models list at `platform.claude.com/docs/en/build-with-claude/effort` and marked "Not supported" in the models-overview comparison table. An agent may still declare an `effort` value in `agents.yaml`; it only becomes meaningful if the agent later resolves to a model whose `effort_support` is `true`.

---

## Checklist

- [ ] Added an entry to the right provider block in `agent_notes/data/catalog/seed.json` (`id`, `coding_index`, `price_in`, `price_out`, `rank`, ...)
- [ ] `id` matches an existing `families:`/`classes:` glob in `rules.yaml`, or new globs were added for it
- [ ] If the provider needs a non-default alias format, added an `alias_overrides` (or `alias_transforms`) entry in `rules.yaml`
- [ ] The model's alias-provider key matches at least one CLI's `accepted_providers`
  - Check with: `python3 -c "from agent_notes.registries.cli_registry import load_registry; [print(c.name, c.accepted_providers) for c in load_registry().all()]"`
- [ ] `coding_index` set (or explicitly left `null` if genuinely unrated) — a `null` model is never auto-selected
- [ ] Ran `agent-notes list models` and saw the new model under its provider
- [ ] Ran `agent-notes install` and the model appears in step 2 for compatible CLIs

---

## Next Steps

- **Add a new role** if you want a role with a different `budget` ceiling for this model to default under: see `docs/ADD_ROLE.md`.
- **Update CLI_CAPABILITIES.md** with details about the model's provider if relevant.
- **Set role**: `agent-notes set role <role> <model-id> --cli <cli>` to pin the model post-install.

