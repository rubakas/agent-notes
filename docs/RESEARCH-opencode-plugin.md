# Research: OpenCode plugin support

## Summary

OpenCode DOES have a plugin system, but it is fundamentally different from Claude Code's: plugins are JavaScript/TypeScript modules with hooks-based event handlers, installed via npm packages or local files under `~/.config/opencode/plugins/` (or `.opencode/plugins/` per project) and configured in `opencode.json`. Shipping an agent-notes OpenCode plugin requires a new JavaScript entry point — it cannot reuse the existing Claude Code YAML/Markdown plugin architecture.

**Source:** https://opencode.ai/docs/plugins/ **[verified-docs]**

## OpenCode plugin format [verified-docs]

**Manifest:** No JSON manifest file. Configuration is `opencode.json` at project root listing plugin names:
```json
{
  "plugin": ["opencode-helicone-session", "opencode-wakatime", "@my-org/custom-plugin"]
}
```

**Language and export:** JavaScript or TypeScript modules. Plugins export a named async function that returns a hooks object:
```javascript
export const PluginName = async ({
  project,    // project context
  client,     // OpenCode client API
  $,          // shell / command runner
  directory,
  worktree,
}) => {
  return {
    // hooks object with event handlers
  }
}
```

**Install paths:**
- Global: `~/.config/opencode/plugins/`
- Project-local: `.opencode/plugins/`
- npm packages: cached in `~/.cache/opencode/node_modules/`, installed via Bun

**Discovery:** local files in plugin directories load automatically at startup; npm packages listed in `opencode.json` are installed and loaded.

**API surface (hooks):** Command, File, LSP, Message, Permission, Session, Tool, Shell, TUI. Custom tools use a `tool()` helper with Zod schemas.

**Logging:** structured logging via `client.app.log()`.

## Comparison with Claude Code plugin

| Aspect | Claude Code | OpenCode |
|---|---|---|
| Manifest | JSON (`.claude-plugin/plugin.json`) | JSON array in `opencode.json` (project/global) |
| Agent/Skill format | YAML frontmatter + Markdown | N/A — agents/skills are not a native plugin concept |
| Plugin code | Directory structure (`agents/`, `skills/`) | JavaScript/TypeScript module with exported async function |
| Event model | Hooks with matchers + commands | Hooks object with handler functions |
| Install | git clone / marketplace / `.claude-plugin/` | `npm install` or local file discovery |
| Discovery | plugin manager reads `plugin.json` | `opencode.json` config + filesystem scan |
| Primary surface | data layer (agents/skills) | code layer (hooks/tools) |

**Key difference:** Claude Code's plugin model exposes a data layer (YAML agent/skill files). OpenCode's plugin model exposes a code layer (hook handlers). They are not portable to each other.

## Current agent-notes architecture for Claude Code [verified-codebase]

- **Build:** `scripts/build-plugin.sh` reads `pyproject.toml` + `agent_notes/VERSION` + `agent_notes/data/plugin/claude.yaml` (vendored-skills allow-list)
- **Output:** `.claude-plugin/plugin.json` (auto-generated manifest), `.claude-plugin/agents/` (selected agent Markdown), `.claude-plugin/skills/` (vendored skill Markdown)
- **Install:** users `pip install agent-notes` or clone the repo, then run `agent-notes install`

## Implementation plan for an agent-notes OpenCode plugin [verified-docs + design]

1. **JavaScript entry point** (new): `agent_notes/data/plugin/opencode.js` (template) → emitted to `.opencode-plugin/index.js`. Exports `export const AgentNotes = async (context) => { return { /* hooks */ } }`. Initial scope: a single `SessionStart` hook that sources agent-notes context (parallel to the existing Claude Code SessionStart hook in `plugin.json`).

2. **Build step**: extend `scripts/build-plugin.sh` with an `--opencode` flag, OR add a sibling `scripts/build-opencode-plugin.sh`. Templates the JS entry point; reads `pyproject.toml` for metadata; emits `.opencode-plugin/`.

3. **Distribution options:**
   - **Local install** (simpler): commit `.opencode-plugin/` and document in README — users symlink/copy to `~/.config/opencode/plugins/agent-notes/` or add the project path to `opencode.json`.
   - **npm publishing** (later, when demand exists): add `package.json` with `"main": ".opencode-plugin/index.js"`, `"type": "module"`; publish as `@rubakas/agent-notes-opencode-plugin`; users add `"plugin": ["@rubakas/agent-notes-opencode-plugin"]` to their `opencode.json`.

4. **Tests:** `tests/integration/test_opencode_plugin_build.py` — verifies JS entry point exists, exports a callable, hooks object structure is valid (parse the JS without executing).

5. **`pyproject.toml` package-data:** include `.opencode-plugin/` if shipping via the Python wheel; otherwise leave excluded.

## What this does NOT provide [verified-docs]

An OpenCode plugin cannot expose agent-notes' agents and skills the way Claude Code does, because OpenCode does not treat agents/skills as a plugin concept. In an OpenCode plugin:
- Agents would be invoked as shell commands or utility functions inside hook handlers
- Skills would be source files in the plugin repo, not auto-discovered
- The plugin primarily serves as a setup/initialization hook, not a skill provider

The Python CLI (`pip install agent-notes && agent-notes install`) remains the canonical OpenCode distribution path; a JS plugin is a secondary integration.

## What `.opencode/` is in this repo [verified-codebase]

- `.opencode/AGENTS.md` is placeholder text only.
- Directory mirrors Claude Code's `.claude/` shape but contains no packaged content.
- Generated by `agent-notes build` and populated by `agent-notes install --local`.
- Not used by CI or the PyPI package; not in `pyproject.toml` `package-data`.
- The new OpenCode plugin should live at `.opencode-plugin/` (separate from this dev scaffold) to avoid overloading.

## Open questions for the user

1. **Plugin priority:** ship an OpenCode plugin in Phase 8.D, or stay with the Python CLI as the canonical OpenCode path?
2. **Scope:** minimal SessionStart hook only, or also bridge agent-notes commands into OpenCode tools?
3. **Distribution:** local install (commit `.opencode-plugin/` + docs) or npm package?
4. **Agents/skills bridging:** any appetite for surfacing agent-notes skills as OpenCode tools (would require Zod schemas per skill)?

## Recommendation

- **Status:** unblocked; ready to implement when prioritized.
- **Effort:** small (~5–8 hours) for a minimal SessionStart hook + build script + smoke test.
- **Risk:** low — no shared state with the Claude Code plugin; failures are isolated to the new artifact.
- **Suggested approach:** local install first (commit `.opencode-plugin/index.js`); document under README "Install Methods → OpenCode (plugin)"; defer npm publishing until user demand justifies it.
