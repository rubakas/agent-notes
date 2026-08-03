# Component Lifecycle Flag — Design Spec

**Status:** Approved design (brainstorming). Ready for an implementation plan.

**Scope (deliberately thin):** a single cross-cutting *stability* flag on components, plus a local override to force-enable work-in-progress ones during development. This spec does **not** cover the memory `elif`-chain refactor, a uniform component registry, the wizard capability framework, or an `experimental` middle tier — those are separate, later efforts. This flag is the small unblocking piece, and the tool that makes those larger refactors landable incrementally.

**Relationship to other specs:** sibling to `2026-07-31-wizard-capability-framework-design.md` (which reorganizes the install wizard). This flag is independent of that and useful on its own; the wizard framework, if built, would simply consume the same visibility filter.

## Problem

agent-notes is a shared template of AI-provider backends, memory providers, skills, and agents, generated for CLI usage. New providers/backends get added and old ones removed over time. Today there is **no way to commit a half-built component** so that it lives in the tree, stays out of the build/wizard/user-facing listings, and doesn't break tests — while a developer toggles it on to work on it.

The research (2026-07-31) confirmed the gap. Existing gating is all either:
- **per-user config** — `enabled_plugins` map (plugins on/off), chosen by the user;
- **per-backend capability** — `backend.supports(requires)` / `backend.features`, hardcoded per backend;
- **catalog-level** — `never_default` / `deprecated` on models (available but not auto-selected);
- **hardcoded removal** — `memory/memory_backend.py` `_REMOVED_BACKENDS` (raises on access).

None of these is a **development-time stability marker** that hides a component from *all* users while it's being built, is committed to the repo (so CI and teammates see it), and can be force-enabled per checkout. That is what this flag adds.

Consequence today: a developer adding, say, a "gemini" backend must either commit it fully visible (it ships broken), hide it on a long-lived branch (it blocks and rots), or abuse `deprecated`/`never_default` (leaves it in the registry, unusable). Work on one component blocks the system.

## The model — a `stability` field, two states

Every component a developer can add incrementally gains one optional field, `stability`, declared in the manifest that family *already* uses. No new registry, no new file type.

- **`stable`** — the default, and what every current component implicitly is. Visible and built normally.
- **`wip`** — excluded from the wizard, the build output, and every user-facing listing (invisible to users) **unless the local override names it**. This is the "half-built, committed, not shipped" state.

The field is a string enum. A third tier — `experimental` (shipped but opt-in only) — can be added later with zero migration; it is explicitly out of scope now (nothing needs the middle tier yet).

**Default rule:** absence of the field ⇒ `stable`. This is what makes the change byte-identical for the existing tree.

## Where the field lives, per family

Each in the family's existing manifest, parsed into the family's existing domain object:

| Family | Manifest location | Domain object gaining `stability` |
|---|---|---|
| AI provider / CLI backend | `data/cli/<name>.yaml` top-level `stability:` | `domain/cli_backend.py` `CLIBackend` |
| Memory provider | class attribute on the backend registered in `memory/memory_backend.py` `_REGISTRY` | the backend class (`local_backend.py` / `obsidian_backend.py` / …) |
| Plugin / toggle | `data/plugins/<name>/plugin.yaml` `stability:` | `domain/plugin.py` `Plugin` |
| Skill | `data/skills/<name>/SKILL.md` frontmatter `stability:` | `domain/skill.py` `Skill` |
| Agent | `agents.yaml` per-agent `stability:` | `domain/agent.py` `AgentSpec` |

Each loader (`cli_registry`, `skill_registry`, `agent_registry`, `plugin_registry`, the memory backend registry) reads the value and validates it against the enum, defaulting to `stable`.

## The local override

A single environment variable:

```
AGENT_NOTES_ENABLE_WIP=gemini,notion agent-notes build
```

- Comma-separated component names treated as **visible** for this process only.
- Ephemeral, per-shell — impossible to commit by accident.
- CI can set it to exercise a `wip` component's own tests without exposing it to users.
- Names match the component's declared `name` (backend name, provider name, plugin name, skill name, agent name). Namespacing across families is not required now — names are unique enough in practice; a `wip` name simply matches whichever component(s) carry it. (A future `family:name` form can disambiguate if a collision ever arises.)

A gitignored `dev.yaml` could back this later; the env var is sufficient now and avoids a new file format.

## Mechanics — one cross-cutting visibility filter

A single new helper is the whole mechanism. Suggested home: a small module, e.g. `agent_notes/services/stability.py`:

```
def enabled_wip() -> frozenset[str]:
    """Component names force-enabled via AGENT_NOTES_ENABLE_WIP (may be empty)."""

def is_visible(stability: str, name: str, override: frozenset[str]) -> bool:
    """True unless stability == 'wip' and name not in override."""
```

Every registry that enumerates components **for user-facing purposes** routes its "list for wizard / build / listing" path through `is_visible`:

- `cli_registry` — the set of backends offered/built.
- memory backend registry — the providers offered in the wizard / `config memory`.
- `plugin_registry` — `plugins list` and the enabled/contributed set.
- `skill_registry` — skills routed into the build.
- `agent_registry` — agents rendered into the build.

**Selection guard:** a `wip` component that is not overridden must never be *selectable*. Enumeration points filter it out (so it never appears as an option); any direct exact-name resolution path used internally should refuse a hidden component so a stale state file can't select one. Concretely: filter at enumeration; guard at selection.

**Overridden `wip` builds normally.** When `AGENT_NOTES_ENABLE_WIP` names a component, it is treated exactly like a `stable` one — offered in the wizard, built into `dist/`, listed. This is the point: a developer flips it on and exercises the real wizard → build → dist pipeline end to end.

Net footprint: **one field per manifest, one helper, ~5 filter call-sites.**

## Compatibility & equivalence

Byte-identical by construction: every existing component defaults to `stable`, and with no override every enumeration path yields exactly today's set. Verified at each task boundary with `scripts/dev/verify_dist_equiv.sh <baseline>` — the committed checksum-vs-baseline gate. **Never** use `git diff` / `git status` on `agent_notes/dist/` to check equivalence: that tree is gitignored, so those always report empty and would be a no-teeth gate.

## Testing

Extend the existing hermetic CLI smoke suite (`tests/functional/commands/test_plugins_cli.py` pattern: subprocess-driven, per-test `XDG_CONFIG_HOME`, real user config asserted untouched). Per family, and at the CLI level:

1. **Hidden by default** — a fixture component marked `stability: wip` is absent from the wizard options, the build output, and the relevant `list` command when `AGENT_NOTES_ENABLE_WIP` is unset.
2. **Visible when overridden** — the same component appears and builds when `AGENT_NOTES_ENABLE_WIP` names it.
3. **Selection guard** — attempting to select/resolve the hidden component by exact name without the override fails (not silently succeeds).
4. **Enum validation** — a loader rejects an unknown `stability` value with a clear error.
5. **Hermeticity** — the env var is set per-test; the real `~/.config` is never touched.

A `wip` fixture component should be introduced for tests rather than marking a real shipped component `wip` (which would change dist).

## Optional: `doctor` visibility

Add one line to `agent-notes doctor`: list any components declared `wip` and whether `AGENT_NOTES_ENABLE_WIP` is currently enabling them. This answers the predictable support question — "why isn't my new backend showing up?" — and surfaces override typos (see Risks).

## Non-goals

- The memory `elif`-chain refactor / uniform component registry (separate brainstorm).
- The wizard capability framework (separate spec).
- The `experimental` middle tier (add later; enum leaves room).
- A file-backed override, per-family name namespacing, or a plugin-marketplace/versioning notion.
- Any change to model-catalog gating (`never_default` / `deprecated` stay as they are — they solve a different, catalog-specific problem).

## Risks

1. **A `wip` component leaks** if a registry's user-facing path forgets to route through `is_visible`. *Mitigation:* centralize on the single helper; the "hidden by default" test per family is the regression guard.
2. **Override typo silently does nothing** — `AGENT_NOTES_ENABLE_WIP=gemni` leaves `gemini` hidden with no error. *Mitigation:* the `doctor` line; optionally emit a warning when the override names a component that matches nothing.
3. **"User-facing" is fuzzy for internal callers.** Some registries feed both the build and internal resolution. *Mitigation:* default the filter ON at enumeration points and keep exact-name resolution direct but selection-guarded, so a hidden component can be *resolved by name only when already legitimately chosen* — which, with the enumeration filter, it never is unless overridden.
4. **Scope creep toward the god-registry.** This flag is intentionally not the uniform-registry refactor. *Mitigation:* keep the field and helper family-agnostic but add nothing beyond `is_visible`; resist folding the memory de-`elif` in here.
