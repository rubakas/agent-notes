# Codex CLI Support — Progress Tracker

> Working/orchestration doc. Survives session disconnect or context-clear. Delete before release.
> Goal: add first-class Codex CLI support to agent-notes (originally "Tier 2 full: agents + skills + prompts + AGENTS.md + hooks, complete and ready").

Last updated: 2026-06-14 (codex upgraded to 0.139.0 — hooks blocker LIFTED)

## Status: COMPLETE ✅ (full parity implemented, verified end-to-end against Codex 0.139). Not committed (awaiting user). This tracker can be deleted before release.

### FINAL RESULT (verified)
- 1541 tests pass (15 deselected = network/build/clean-repo marks). 265 new codex tests.
- build → 19 dist/codex/agents/*.toml + dist/codex/AGENTS.md (lead excluded). claude/opencode byte-identical.
- temp install: agents(.toml) + AGENTS.md + 23 skills + hooks.json(SessionStart) land correctly; all toml parse.
- `CODEX_HOME=$TMP codex doctor` (0.139): config loads clean, no agent/hook/skill errors. hooks + multi_agent enabled. SKILL.md extra-frontmatter (group/requires_memory) tolerated — no errors.
- Reviewer findings all fixed: (1) preferred_family added (codex=gpt, opencode/claude=claude) so gpt models no longer hijack opencode resolution; (2) wizard install_agents_filtered uses _agent_glob; (3) _apply_overrides claude guard restored; (4) wizard installs codex SessionStart hook; (5) render_globals loop substitutes {{MEMORY_INSTRUCTIONS}}.

### Files (final)
NEW: data/cli/codex.yaml; data/templates/frontmatter/codex.py (emit_file->TOML); data/global-codex.md; data/models/{gpt-5-5,gpt-5-4,gpt-5-4-mini}.yaml; tests/plugins/codex/test_agents.py; tests/unit/templates/test_codex_frontmatter.py; tests/unit/registries/test_cli_registry.py (codex cases); tests/unit/services/test_installer_codex.py.
MODIFIED: services/rendering.py (emit_file dispatch + render_globals loop + preferred_family fallback + MEMORY_INSTRUCTIONS sub); services/installer.py (_agent_glob, _hooks_filename, codex hook funcs, codex branches, _apply_overrides guard restored); domain/cli_backend.py (preferred_family); registries/cli_registry.py (preferred_family, hooks layout); data/cli/{opencode,claude}.yaml (preferred_family); data/cli/codex.yaml (hooks layout); commands/wizard/execute.py (_agent_glob + codex hook); data/agents/agents.yaml (lead codex_exclude); pyproject.toml (tomli-w).

### Known follow-ups (non-blocking)
- gpt model IDs (gpt-5.5/5.4/5.4-mini) match installed 0.139 models_cache; update if OpenAI renames.
- conftest.py uses bare `python3` subprocess → needs venv python first on PATH to run tests (pre-existing env quirk, not codex-related).

### UPDATE — Codex upgraded 0.133.0 -> 0.139.0
`codex features list` (authoritative):
- `hooks` = STABLE, true  ✅ (was the blocker; now usable)
- `multi_agent` (subagents) = STABLE, true  ✅
- `plugins` = stable true; `plugin_hooks` = REMOVED → hooks NOT via plugin.json manifest; use standalone `~/.codex/hooks.json` or config.toml `[hooks]`
- `skill_mcp_dependency_install`, `plugin_sharing` = stable
- `child_agents_md` = under development (project AGENTS.md for child agents — not stable)
Hooks are trust-gated: `codex --dangerously-bypass-hook-trust` skips trust; normal flow persists hook trust on first run.
Working hooks.json format (from bundled figma plugin) — IDENTICAL to Claude settings.json hooks:
  {"hooks":{"PostToolUse":[{"matcher":"Write|Edit","hooks":[{"type":"command","command":"./scripts/..."}]}]}}
Codex CLI subcommands: exec, review, mcp, plugin, features, doctor, sandbox, resume, fork, cloud, ...
STILL TO CONFIRM AT IMPL TIME: (a) exact subagent file dir+format in 0.139 (multi_agent stable but ~/.codex/agents/ not yet created on disk; public docs say standalone agent files name/description/developer_instructions=\"\"\"...\"\"\"/model/model_reasoning_effort/sandbox_mode); (b) user-scope hooks path (~/.codex/hooks.json global vs config.toml [hooks]) + trust persistence flow; (c) custom prompts still unconfirmed (likely out of scope).

---

## VERIFIED FINDINGS (ground truth — do not re-investigate)

### agent-notes architecture (already abstracts host CLIs)
- CLI backends are data-driven: YAML descriptors in `agent_notes/data/cli/*.yaml` (existing: claude, opencode, copilot).
- `agent_notes/domain/cli_backend.py` — `CLIBackend` dataclass. Fields: name, label, global_home(Path), local_dir, layout(dict component→dir), features(dict), global_template, exclude_flag, strip_memory_section(bool), settings_template, accepted_providers(tuple), use_model_class(bool). Methods: `supports(feature)`, `first_alias_for(model_aliases)`, `with_local_dir`, `with_global_home`.
- `agent_notes/registries/cli_registry.py` — required fields: name, label, global_home, layout, features. Reads accepted_providers via `.get(...,[])`→tuple.
- Frontmatter plugins: `agent_notes/data/templates/frontmatter/{claude,opencode}.py` — contract `render(ctx)->str` + `post_process(prompt,ctx)->str`. ctx keys: agent_name, agent_config, model_str, backend_name, backend. Dispatched by `features.frontmatter: <name>` (must be valid py identifier).
- `agent_notes/services/rendering.py:render_globals()` (~line 414) — HARDCODED per backend (claude/opencode/copilot). New backend needs a branch OR refactor to loop `registry.all()` using `config.global_template_path`/`global_output_path` (both exist, config.py:90-101).
- `agent_notes/commands/build.py:copy_commands()` (~line 60) — HARDCODED `dist/claude/commands`. Generic per-backend dist build otherwise.
- `agent_notes/services/installer.py` — hook plumbing GATED on `registry.get("claude")` in plan_install (~310), install_all (~339), uninstall_all (~415). Helpers: `_session_hook_paths` (~434), `_install_session_hook`, `_plan_session_hook`, `target_dir_for`, `config_filename_for`.
- `agent_notes/services/settings_writer.py` — Claude JSON hook writer (settings.json). install_hook/remove_hook/has_hook/install_allow_entry idempotent. JSON-only.
- `agent_notes/commands/wizard/__init__.py:_select_cli` (~62) — fully registry-driven; new backend appears automatically. default safe set = {"claude"}.
- Model registry: `agent_notes/data/models/*.yaml`. Aliases present: `anthropic`, `github-copilot` ONLY. **NO `openai` alias on any model.** All models are Claude models.
- Deps (pyproject.toml): pyyaml, tomli (py<3.11). `tomlkit` NOT present. requires-python >=3.10.

### Codex CLI v0.133.0 (INSTALLED locally at ~/.codex — GROUND TRUTH)
Binary: `/Users/vzelenko/.nvm/versions/node/v22.18.0/bin/codex`, `codex-cli 0.133.0`. config model = `gpt-5.5`.
- **Skills** ✓ — `~/.codex/skills/<name>/SKILL.md` = markdown + YAML frontmatter (name, description, optional metadata) — ~IDENTICAL to Claude SKILL.md. Optional `agents/openai.yaml` (interface: display_name, short_description, icons, default_prompt) = UI metadata, NOT a subagent. System skills under `~/.codex/skills/.system/`.
- **AGENTS.md** ✓ — `~/.codex/AGENTS.md` (global, currently 0 bytes) + project `./AGENTS.md`. Instructions file ≈ CLAUDE.md. (opencode also uses AGENTS.md but installs to its own home — no collision.)
- **MCP** ✓ — `[mcp_servers.<id>]` in config.toml (command, args, startup_timeout_sec, [.env]).
- **Hooks** ✗ NOT IMPLEMENTED in 0.133 — plugin-json-spec states "Validation rejects unsupported manifest fields such as hooks". No `[hooks]` in config.toml. (Public dev docs DO describe hooks: hooks.json / [[hooks.PreToolUse]] with matcher/type/command/timeout/statusMessage, events SessionStart/PreToolUse/PostToolUse/etc. — but installed runtime rejects them.)
- **Subagents-as-files** ✗ UNCONFIRMED in 0.133 — no `agents/` dir. Public subagents doc claims standalone files (`name`, `description`, `developer_instructions="""..."""`, model, model_reasoning_effort, sandbox_mode, mcp_servers) but on-disk evidence absent. Risky.
- **Rules** ✗ — `~/.codex/rules/default.rules` is a custom DSL (`prefix_rule(pattern=[...], decision="allow")`), NOT markdown. agent-notes markdown rules DO NOT map → rules:false.
- **Custom prompts / slash commands** ✗ — no `prompts/` dir, no format found in 0.133.
- **Plugins/marketplaces** = real extension mechanism: `~/.codex/.tmp/bundled-marketplaces/openai-bundled/plugins/<name>/.codex-plugin/plugin.json` + `marketplace.json`. Plugins bundle skills/scripts/assets/mcp; plugin.json has name/version/description/interface(displayName,...)/skills path.
- DO NOT READ `~/.codex/auth.json` (credential file).

### Conflict
Public Codex dev docs (hooks + TOML subagents + prompts) ≠ installed Codex 0.133 (skills/AGENTS.md/MCP/plugins; NO hooks, no agent files, no prompts). Different lineages / feature flux. "Tier 2 full with working hooks" is NOT achievable against installed 0.133 — runtime rejects hooks.

---

## DECISIONS (user-approved)
- Scope = **FULL PARITY**: subagents + skills + AGENTS.md + hooks + MCP.
- Model mapping = **MAP TO OPENAI MODELS** (add gpt-5.x model YAMLs; accepted_providers=[openai]; subagents get model + model_reasoning_effort).
- Target Codex **0.139.0**.

## CONFIRMED FORMATS (empirically validated via `codex doctor` on throwaway CODEX_HOME — authoritative)
- **Subagents**: `~/.codex/agents/<name>.toml` (global) / `.codex/agents/<name>.toml` (project). AUTO-DISCOVERED, no config.toml registration needed. `.md` files IGNORED — must be `.toml`.
  Fields: `name`(req, ASCII letters/digits/space/-/_), `description`(req), `developer_instructions`(req, multiline `"""..."""` = THE PROMPT BODY), optional `model`, `model_reasoning_effort`(minimal|low|medium|high|xhigh), `sandbox_mode`(read-only|workspace-write|danger-full-access), `nickname_candidates`(array).
  Conflict: same name in config.toml [agents.x] AND agents/x.toml => "duplicate agent role" error. Use one mechanism. WE USE standalone agents/<name>.toml.
- **Hooks**: `~/.codex/hooks.json` (global, JSON). SAME shape as Claude settings.json hooks: {"hooks":{"SessionStart":[{"matcher":"","hooks":[{"type":"command","command":"..."}]}]}}. Events incl SessionStart/PreToolUse/PostToolUse/Stop/UserPromptSubmit/Subagent*. Trust: global ~/.codex is user-level (trusted); project .codex hooks need projects.<path>.trust_level="trusted". `--dangerously-bypass-hook-trust` skips. => settings_writer.install_hook works directly on hooks.json (no new TOML dep for hooks).
- **Skills**: `~/.codex/skills/<name>/SKILL.md` markdown+frontmatter; requires name+description. Extra keys (group/requires_memory) tolerance UNVERIFIED — test at impl; strip for codex if it errors. Shared dist/skills install path.
- **AGENTS.md**: `~/.codex/AGENTS.md` global + `./AGENTS.md` project = instruction file (config-reference confirms default; model_instructions_file overrides; project_doc_fallback_filenames; project_doc_max_bytes cap).
- **OpenAI models** (from ~/.codex/models_cache.json): gpt-5.5 (frontier), gpt-5.4, gpt-5.4-mini. reasoning efforts minimal|low|medium|high|xhigh.

## FINAL PLAN (full parity)
NEW files:
1. `agent_notes/data/cli/codex.yaml` — descriptor: global_home ~/.codex, local_dir .codex, layout{agents:agents/, skills:skills/, config:AGENTS.md}, features{agents:true,skills:true,rules:false,commands:false,memory:false,frontmatter:codex}, global_template:global-codex.md, exclude_flag:codex_exclude, strip_memory_section:true, accepted_providers:[openai], use_model_class:false.
2. `agent_notes/data/templates/frontmatter/codex.py` — implements NEW optional `emit_file(ctx, body)->(filename, content)` returning (`<name>.toml`, tomli_w.dumps({name,description,developer_instructions=body, model, model_reasoning_effort, sandbox_mode})). post_process strips "## Memory"/"## Cost reporting" (reuse opencode logic). reasoning_effort from agent `effort`; sandbox_mode derived (writer agents->workspace-write, read-only->read-only).
3. `agent_notes/data/global-codex.md` — AGENTS.md global = primary/orchestrator instructions adapted (model opencode/claude global; include partials). Exclude `lead` subagent for codex (its role lives here).
4. `agent_notes/data/models/gpt-5-5.yaml`(class opus), `gpt-5-4.yaml`(class sonnet), `gpt-5-4-mini.yaml`(class haiku) — aliases{openai: gpt-5.5 / gpt-5.4 / gpt-5.4-mini}, family gpt, pricing/capabilities. (classes reuse opus/sonnet/haiku so role.typical_class resolution picks them for openai provider; no cross-talk with claude since gpt models have no anthropic alias.)
5. Tests: tests/plugins/codex/test_agents.py (toml agents valid, has name/description/developer_instructions, model contains gpt), unit test for codex.py emit_file, registry test (get("codex"), supports), installer test (agents .toml copy + hooks.json SessionStart), hook reuse test.

MODIFY:
6. `agent_notes/services/rendering.py` — (a) in generate_agent_files: if frontmatter template exposes `emit_file`, use it for filename+content instead of `frontmatter+"\n\n"+body`+`.md`; (b) render_globals: add codex (prefer refactor to loop registry via config.global_template_path/global_output_path).
7. `agent_notes/services/installer.py` — (a) agent component copy: handle `.toml` (codex) not just `*.md` (per-backend agent glob, or copy all); (b) generalize claude-gated SessionStart hook blocks (plan_install ~310, install_all ~339, uninstall_all ~415) to ALSO install codex hook into ~/.codex/hooks.json via settings_writer, context file ~/.codex/agent-notes-context.md.
8. `pyproject.toml` — add `tomli-w` dep (agent .toml emission). Hooks reuse settings_writer (JSON) — no tomlkit needed.
9. agents.yaml — NO change required (sandbox/effort derived). Optional `codex:` per-agent block can be added later.

VERIFY (end-to-end on installed 0.139):
- `python -m agent_notes build` (or build cmd) → dist/codex/agents/*.toml, dist/codex/AGENTS.md exist.
- Install to a throwaway CODEX_HOME, run `CODEX_HOME=$TMP codex doctor` → no agent/hook validation errors, agents discovered.
- Full pytest suite green.

## DONE
- [x] Mapped agent-notes CLI-backend abstraction
- [x] Verified Codex public-docs config surface
- [x] Codex upgraded 0.133->0.139; hooks+multi_agent now STABLE
- [x] Empirically confirmed subagent .toml format, hooks.json shape, model list
- [x] Confirmed agent-notes rendering/install integration points
- [x] User decisions: full parity + map-to-openai-models

## TODO (implementation)
- [x] codex.yaml descriptor
- [x] codex.py frontmatter/emitter (emit_file -> TOML) + rendering.py emit_file support
- [x] global-codex.md + render_globals loop refactor
- [x] gpt-5.x model YAMLs (gpt-5-5 opus / gpt-5-4 sonnet / gpt-5-4-mini haiku, openai aliases)
- [x] pyproject tomli-w dep (installed in pipx venv too)
- [x] lead excluded from codex (codex_exclude:true). Build OK: 19 dist/codex/agents/*.toml + dist/codex/AGENTS.md. claude/opencode byte-identical. 88 tests pass. Models resolve to gpt-5.x.
- [ ] installer: .toml agent copy + codex hooks.json wiring  <-- IN PROGRESS
- [ ] tests (codex plugin, registry, installer, emitter)
- [ ] build + verify against `codex doctor` (throwaway CODEX_HOME)
- [ ] verify SKILL.md extra-frontmatter tolerance on codex; strip if needed
- [ ] full pytest green
- [ ] reviewer pass
