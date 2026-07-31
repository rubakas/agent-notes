# Wizard Capability Framework — Design Spec

**Status:** Approved for implementation (owner, 2026-08-01) — this is how epic #32's **#40** is built (superseding its stale "collapse two wizard steps / 9→8" framing). The four open questions are resolved below; build proceeds in the six byte-identical phases in "Suggested phasing". The implementation plan follows in `docs/superpowers/plans/`.

**Author context:** written after establishing (with the owner) that agent-notes' pluggable things fall into four kinds, and that the CLI backends *are* the multi-select "AI-provider plugins."

## Problem

The install wizard is a hardcoded imperative sequence: `TOTAL_STEPS = 9`, a fixed list of `_select_*(step=N, total=9)` calls, values threaded explicitly into `_execute_install`. Every configurable subsystem is bespoke: memory is step 7, cost-report is step 8, backends are step 1, models/effort step 2. Adding or removing a configurable feature means editing the orchestrator, renumbering steps, and threading new params.

Three decisions make a general model both necessary and possible:
1. **cost-report is a plugin** (toggle) but still has a hardcoded wizard step.
2. **memory is a provider** (local/obsidian, single-select), not a toggle — it needs its own view + logic, always present.
3. **the CLI backends are the "AI-provider plugins"** — claude (anthropic), codex (openai), opencode (both), copilot — already multi-select, already generate one `dist/<backend>/` per selection. They should be first-class capabilities in the same framework.

The goal: a wizard that **composes its step list dynamically from the selected capabilities**, where each capability declares its own view(s) and processing logic, and adding a capability costs zero orchestrator edits.

## The four capability kinds

| Kind | Selection | On install | Wizard presence | Config view | Examples |
|---|---|---|---|---|---|
| **Backend** | multi-select | generates `dist/<name>/` per selection | selection step + per-backend config | yes (models/effort per role) | claude, codex, opencode, copilot |
| **Provider** | single-select (exactly 1 of N, per slot) | selects one implementation for a slot | config step (always present) | yes (per provider) | memory: local / obsidian |
| **Toggle** | on/off (multi) | enabled → contributes hooks/includes/skills | in the enable/disable step; optional config step when on | optional | cost-report |
| **Core** | none (always on) | always installed | hidden | none | credential guard |

Key distinctions the model must preserve:
- **Backend = multi**, **Provider = single**. A user installs for claude AND codex (both), but chooses exactly one memory implementation.
- **Provider is a "slot"**: `memory` is a slot whose options are the providers `local`/`obsidian`. The framework allows future slots (e.g. a hypothetical `secrets` slot) without special-casing memory.
- **Toggle ≠ Provider**: you can't "disable" memory (a provider slot always resolves to one option — `local` is the floor); you can disable cost-report.
- **Core is invisible**: never offered, never disable-able (a menu-toggleable safety guard is a regression).

## The seam: data manifests + code-side view/logic registry

The `devil` already rejected putting callables in YAML (it turns "manifest is data" into an import/code-exec vector). So the split is:

- **Manifest (data)** — what a capability *is*: `name`, `kind` (backend|provider|toggle|core), `default` (toggle default / provider default option / backend default-selected), `order` (a phase/priority hint for step placement), and for toggles the existing contribution fields (skills, includes, hooks, allow). Backends keep `data/cli/*.yaml`; toggles keep `data/plugins/*/plugin.yaml`; providers get `data/providers-slots/` (or reuse existing config).
- **Code registry (behavior)** — *how* a capability behaves: a Python registry maps `capability name → { view: fn, process: fn }`. `view` runs the interactive wizard screen(s) and returns a config dict; `process` applies that config (writes state, installs hooks, renders). Capabilities register in code; manifests never name a callable.

This mirrors what already exists (backends have `cli_registry` + rendering logic; memory has backend modules; cost-report has a manifest + installer wiring) — the framework *unifies* those into one registration surface rather than inventing new machinery.

## Dynamic wizard composition

The orchestrator stops being a fixed sequence and becomes a **composer**:

```
1. GENERAL install steps (not capability-owned): scope, mode, profile.
   These decide WHERE/HOW to install, independent of capabilities.

2. SELECTION steps:
   - Backend selection (multi): which backend-plugins? (today's step 1)
   - Toggle selection (on/off): which toggle-plugins? (cost-report + future)
   Providers are NOT selected here — a slot is configured in its own step.

3. CONFIG steps — built dynamically from the selections above, in `order`:
   - For each SELECTED backend that has a config view → its view
     (models/effort per role — today's step 2, per backend).
   - For each PROVIDER slot → its view: pick the one option (local/obsidian),
     then that option's provider-specific screen (obsidian → strategy + path;
     local → nothing).
   - For each ENABLED toggle that declares a config view → its view
     (cost-report: none today).

4. Confirm (shows the composed selection) + build (per selected backend).
```

`TOTAL_STEPS` is **computed** after the selection steps, not a constant. Step numbering (`N/total`) is derived from the composed list. Enable a future toggle with a config screen → its step appears; deselect a backend → its config step disappears.

## How today's pieces map (and what stays byte-identical)

- **Backends** (claude/codex/opencode/copilot): already `data/cli/*.yaml` + `cli_registry` + per-backend rendering. Wrapped as `kind: backend`. Selection = today's step 1; per-backend model/effort = today's step 2 (its `view`). **No change to what each backend generates.**
- **Memory** (local/obsidian + strategy): the `memory` provider slot. `view` = the M3 provider→strategy flow (already built). `process` = the existing memory install/instructions logic. Single-select preserved.
- **cost-report**: `kind: toggle`, `default: off`, no config view. Selection moves into the toggle step; the standalone `_select_cost_report` step retires.
- **cred-guard**: `kind: core`. Never in the wizard; installs unconditionally as today.
- **General steps** (scope/mode/profile/skills): remain general (not capability-owned) — they configure the install, not a capability. (Open question: is skills a cross-cutting selection or its own capability? See below.)

**Compatibility contract:** an install that reproduces today's default choices MUST produce today's `dist/` and `settings.json` — verified with `scripts/dev/verify_dist_equiv.sh` (never `git diff` on the gitignored dist). The framework reorganizes *how* steps are composed, not *what* equivalent selections produce.

## Suggested phasing (for the implementation plan, post-approval)

1. **Framework skeleton**: `Capability` type (kind, manifest fields), a `capability_registry` (view/process), a `WizardStep` abstraction, and a composer that runs a static list (no behavior change yet) — pure scaffolding, byte-identical.
2. **Migrate toggles**: cost-report becomes a registered toggle; its wizard step is composed, not hardcoded. Retire `_select_cost_report`.
3. **Migrate the memory provider slot**: the M3 flow becomes the memory provider's `view`.
4. **Migrate backends**: backend selection + per-backend config become composed capability steps (the biggest step — step 1 + step 2 are central).
5. **Dynamic numbering + confirm**: `TOTAL_STEPS` computed; confirm screen renders the composed selection.
6. **Docs**: how to add a capability of each kind.

Each phase is byte-identical for equivalent selections and independently reviewable.

## Risks

1. **This is a large refactor of the most central UX.** The wizard + `_execute_install` + state flow are load-bearing; a regression breaks every install. Mitigation: phase it, keep each phase byte-identical, lean on the hermetic CLI smoke suite (extend it per phase).
2. **Premature generality.** Today: 4 backends, 1 provider slot (2 options), 1 toggle, 1 core. The framework earns its keep as capabilities grow; right now it mostly *reorganizes* a near-fixed sequence. Accepted deliberately by the owner ("full engine now"), but the plan should keep the abstraction as thin as the four kinds require — no speculative extension points beyond them.
3. **Data/code split drift.** Two registration surfaces (manifest + code registry) can disagree (a manifest with no registered view, or vice-versa). The registry loader must validate the pairing and fail loudly.
4. **Backend reconception risk.** Folding step 1/step 2 into the capability framework touches the model-catalog + rendering path (the most complex code). Backends must keep generating exactly what they do now.

## Non-goals

- Not changing the model catalog, pricing, or what any backend renders.
- Not making cred-guard or memory toggle-disable-able.
- Not adding user-supplied/third-party capabilities (built-in only, as with plugins today).
- Not a plugin marketplace or versioning.

## Resolved decisions (owner, 2026-08-01)

The four open questions are settled; #40 is approved to be built as this full framework, phased, each phase byte-identical for equivalent selections.

1. **Skills stay a general step**, not a capability kind. Skills apply across backends and are already a working general selection (today's step 6); a fifth kind is premature. Revisit only if skills gain per-skill configuration.
2. **The `provider` kind is generic but thinly wired.** Implement it as a named slot with options plus a default option, but register only the `memory` slot today. No speculative second slot — the generality lives in the type, not in extra registrations.
3. **Capability-kind jargon stays internal.** Users never see "backend / provider / toggle" as labels. Wizard copy uses friendly, capability-specific wording (e.g. "Which AI tools?", "Memory", "Extras"); the taxonomy lives in code and docs only.
4. **Ordering is by explicit phase**, not a global numeric sort: general → selection → config → confirm. A per-capability `order` is only a tie-break *within* a phase.

## Interaction with the component stability flag (shipped 2026-07-31)

The stability flag (`stability: stable|wip` + `AGENT_NOTES_ENABLE_WIP`) already filters each registry's user-facing enumeration via `available()`. **The wizard composer MUST enumerate selectable capabilities through `available()`, never `all()`**, so a `wip` backend/toggle/provider option stays out of the wizard exactly as it stays out of the build. Hard integration constraint for the selection steps.

## Docs (#41) fold into the final phase

Epic #32's **#41** (plugin docs: the model, writing a plugin, the two meanings of "plugin", plus the provider/core distinction) is written as this framework's documentation phase — describing the finished wizard and the *delivered* plugin/provider/core model (cost-report = toggle, memory = provider, cred-guard = core), not the pre-rescope framing that called memory and cred-guard "plugins".
