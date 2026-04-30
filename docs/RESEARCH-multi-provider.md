# Multi-Provider Model Discovery Research

## Current State

**OpenCode already declares OpenRouter support** [verified-codebase]
File: `agent_notes/data/cli/opencode.yaml` line 22:
```yaml
accepted_providers: [github-copilot, anthropic, openrouter, openai, google, moonshot]
```

**Claude Code is currently Anthropic-only** [verified-codebase]
File: `agent_notes/data/cli/claude.yaml` line 25:
```yaml
accepted_providers: [anthropic, bedrock, vertex]
```

## Implementation Path

### 1. Provider Configuration File

**File to create:** `agent_notes/data/providers/openrouter.yaml`

Proposed schema [training-knowledge — needs manual verification]:
```yaml
name: openrouter
label: OpenRouter
catalog_url: https://openrouter.ai/api/v1/models
auth_env_var: ANTHROPIC_API_KEY
api_base_env_var: ANTHROPIC_BASE_URL
api_base_url: https://openrouter.ai/api/v1
description: Multi-model proxy supporting Claude, GPT, Gemini, Llama, and more
requires_auth_for_catalog: false
pricing_field: pricing
```

OpenRouter exposes an Anthropic-compatible endpoint. Setting `ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1` routes Claude SDK calls through OpenRouter. The `/models` catalog is public; API calls require an OpenRouter API key passed as `ANTHROPIC_API_KEY`.

### 2. Model Discovery Service

**File to create:** `agent_notes/services/model_discovery.py`

```python
def fetch_provider_models(provider_name: str, catalog_url: str) -> list[dict]:
    """
    Fetch available models from a provider's catalog endpoint.

    Returns: list of dicts: {id, name, context_length, pricing, provider}
    Caches by provider_name within a single CLI session.
    """
```

OpenRouter `/models` response shape [training-knowledge]:
```json
{"data": [{"id": "openrouter/openai/gpt-5", "name": "...", "context_length": 128000, "pricing": {"prompt": 0.003, "completion": 0.009}}, ...]}
```

Normalization: model IDs include the provider prefix (e.g. `openrouter/openai/gpt-5`) to disambiguate when multiple providers offer the same model.

### 3. Wizard Integration (Phase 4 hook)

After role selection in `agent-notes config role-model`, call `fetch_provider_models()` for each enabled provider, merge, and display:

```
Select model for role 'lead':
  1. claude-opus-4-7                       (Anthropic, 200K, baseline)
  2. openrouter/anthropic/claude-3-sonnet  (OpenRouter, 200K, ~$2/Mtok)
  3. openrouter/openai/gpt-4-turbo         (OpenRouter, 128K, ~$0.01/Ktok)
```

Store the selected model ID with provider prefix in `state.json`.

## Known Unknowns (need user verification)

1. **[BLOCKED]** Has the user tested `ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1` with Claude Code, and does tool-use still work? Some tool-use features may not survive the proxy.
2. **[BLOCKED]** Exact OpenCode YAML syntax for assigning an OpenRouter model to a role. Need an example from a working `.opencode/` config.
3. **[BLOCKED]** Should `accepted_providers` for Claude Code be expanded to include `openrouter`, or kept Anthropic-only with the proxy implicit?
4. **[BLOCKED]** OpenRouter `/models` rate limits and any User-Agent / API-key requirements for catalog fetches.
5. Should the wizard cache the catalog (and for how long) or fetch fresh on every `agent-notes config` invocation?

## Reference Projects [training-knowledge]

- **aider**: `~/.aider.conf.yml` with `--openrouter` flag; fetches catalog at startup.
- **Continue.dev**: `config.json` with `provider: "openrouter"` per-model entries.
- **cursor**: per-model mapping in settings; provider is implicit per model ID.

All three pull catalog on demand and cache during the session.

## Recommendation for Phase 5.B

**Minimum viable implementation:**

1. `agent_notes/data/providers/anthropic.yaml` — refactor existing models into a provider grouping (built-in, no catalog URL needed).
2. `agent_notes/data/providers/openrouter.yaml` — new descriptor as above.
3. `agent_notes/registries/providers.py` — load provider YAMLs.
4. `agent_notes/services/model_discovery.py` — `fetch_provider_models()` + in-memory cache.
5. `agent_notes/commands/config.py` — wire model discovery into the role-model branch; show provider-prefixed IDs.

**Tests:** mock the `/models` HTTP response; verify discovery merges providers; verify role assignment persists with provider prefix; verify graceful degrade when OpenRouter is unreachable (show built-in models only).

**Before writing code,** resolve open questions 1 and 2 with the user (manual test of `ANTHROPIC_BASE_URL`; OpenCode config example).
