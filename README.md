# agent-notes

AI agent configuration manager for Claude Code and OpenCode — orchestrates a team of 19 specialized subagents across three model tiers.

## Quick Start

```bash
pip install agent-notes
agent-notes install    # interactive wizard guides you through setup
agent-notes doctor
```

**What's Included**
- 19 specialized AI subagents (Opus reasons, Sonnet executes, Haiku explores)
- 50+ on-demand skills (Rails, Docker, Git, Kamal, Process)
- Global rules and guardrails (including a ban on AI self-attribution in commits/PRs)
- Agent memory with 3 storage options (Local, Obsidian, Wiki)
- Configuration for Claude Code, OpenCode, and GitHub Copilot

---

<details>
<summary>Installation</summary>

### PyPI (recommended)

**pipx (isolated environment, no manual venv needed):**

```bash
pipx install agent-notes
agent-notes install
```

**venv + pip (if you prefer to manage your own environment):**

```bash
python -m venv .venv && source .venv/bin/activate
pip install agent-notes
agent-notes install
```

### Upgrade from a previous version

**Update in place (normal upgrade):**

With pipx:
```bash
pipx upgrade agent-notes && agent-notes install
```

With venv:
```bash
pip install --upgrade agent-notes && agent-notes install
```

**Clean reinstall (from an older version, fresh slate):**

If you are on a significantly older version or want a fresh configuration, uninstall completely and reinstall:

With pipx:
```bash
agent-notes uninstall && pipx uninstall agent-notes && pipx install agent-notes && agent-notes install
```

With venv:
```bash
agent-notes uninstall && pip uninstall agent-notes && pip install agent-notes && agent-notes install
```

### Local build (developers)

```bash
git clone https://github.com/rubakas/agent-notes.git
cd agent-notes
pipx install -e .        # editable: CLI runs live from the working tree
agent-notes install
```

With editable mode, the CLI runs directly from your source files. After edits, run `agent-notes install` to rebuild `dist/` and reinstall into your Claude config. No rebuild command needed between iterations.

To produce a release artifact (wheel for distribution), use `python -m build` + `pipx reinstall dist/*.whl` — this is separate from local development.

### Plugin (limited functionality)

- **Claude Code**: install via the Claude Code plugin marketplace or copy/symlink `.claude-plugin/` into `~/.claude/plugins/agent-notes/`.
- **OpenCode**: copy or symlink `.claude-plugin/` into `~/.config/opencode/plugins/agent-notes/` and add `"plugin": ["agent-notes"]` to `opencode.json`.

The plugin runs a `session.start` hook that surfaces agent-notes context to the CLI session. It does **not** include the full `agent-notes` CLI (wizard, doctor, config, memory, etc.). For those, use install method 1 or 2.

### API keys

Provider API keys live in `~/.agent-notes/credentials.toml` (mode 0600, never committed). Add or update via:

```bash
agent-notes config providers
```

The wizard prompts for the key with hidden input; agent-notes never logs or prints the value. To check whether a provider is configured without exposing the key:

```bash
agent-notes config provider openrouter   # prints "configured" or "no key"
```

</details>

<details>
<summary>Uninstall</summary>

To fully remove agent-notes:

**pipx:**

```bash
agent-notes uninstall
pipx uninstall agent-notes
```

Run `agent-notes uninstall` first — it removes agent files, hooks, settings.json entries, context file, and state that agent-notes installed. Then `pipx uninstall` removes the package itself. The `agent-notes uninstall` command must run while the CLI is still installed.

**venv:**

```bash
agent-notes uninstall
deactivate
rm -rf .venv
```

Run `agent-notes uninstall` first to clean up installed components, then deactivate the environment and delete the `.venv` directory.

**Note on memory and vault permissions:**

If you configured agent-notes to access your memory vault (Obsidian or local), those read/write permissions are intentionally left in place after uninstalling so Claude Code and other tools can still access your notes. To remove them, edit `~/.claude/settings.json` and delete the entries under `permissions.allow` that reference your vault path (e.g. `Read(/path/to/your/vault/**)`, `Write(/path/to/your/vault/**)`, `Edit(/path/to/your/vault/**)`).

</details>

---

<details>
<summary>Agent Team</summary>

Specialized subagents with hierarchical model strategy: **Opus 4.8 reasons (high effort), Sonnet 5 executes (medium effort), Haiku 4.5 scouts (low effort).**

| Agent | Role | Model Tier | Purpose |
|---|---|---|---|
| lead | orchestrator | opus | Plans, coordinates, verifies — the team lead |
| architect | reasoner | opus | System design, module boundaries, refactor planning |
| debugger | reasoner | opus | Complex bug investigation, root-cause analysis |
| coder | worker | sonnet | Implementation, file edits, bug fixes |
| reviewer | worker | sonnet | Code quality, readability, correctness |
| security-auditor | worker | sonnet | Auth, injection, XSS, secrets exposure |
| test-writer | worker | sonnet | Creates tests for any framework |
| test-runner | worker | sonnet | Diagnoses and fixes failing tests |
| system-auditor | worker | sonnet | Duplication, dead code, coupling, complexity |
| database-specialist | worker | sonnet | Schema design, indexes, query performance |
| performance-profiler | worker | sonnet | Response times, memory, bundle size |
| api-reviewer | worker | sonnet | REST conventions, versioning, backward compatibility |
| devops | worker | sonnet | Docker, CI/CD, deployment, infrastructure |
| devil | worker | sonnet | Devil's advocate — challenges plans and assumptions |
| integrations | worker | sonnet | OAuth, webhooks, API clients, SSO |
| refactorer | worker | sonnet | Extracts methods, reduces duplication, improves naming |
| explorer | scout | haiku | Fast file discovery, pattern search |
| analyst | scout | haiku | Requirements translation, acceptance criteria |
| tech-writer | scout | haiku | READMEs, API docs, changelogs |

**4 roles, 19 agents, 3 model tiers.** The tiered model strategy optimizes cost: Opus reasons ($5/$25 per 1M tokens in/out), Sonnet executes ($3/$15), Haiku scouts ($1/$5). A premium `fable` tier ($10/$50) is available for explicit pinning, but no role defaults to it.

### Delegation rules

- **lead** — Plans, coordinates, and verifies across the team
- **architect** / **debugger** — Deep reasoning for complex design and debugging
- **coder** — All file edits and implementation work
- **reviewer** — Code quality checks after implementation
- **security-auditor** — Auth, input handling, data access
- **test-writer** — Creates tests; **test-runner** diagnoses and fixes failures
- **system-auditor** — Duplication, dead code, architectural issues
- **database-specialist** — Schema design, queries, indexes
- **performance-profiler** — Latency, memory, bundle size
- **api-reviewer** — REST conventions, versioning, backward compatibility
- **devops** — Infrastructure, CI/CD, Docker
- **integrations** — OAuth, webhooks, API clients
- **refactorer** — Extraction, duplication, naming
- **explorer** — Fast discovery and pattern search
- **analyst** — Requirements and acceptance criteria
- **tech-writer** — Documentation, READMEs, API docs
- **devil** — Challenges assumptions and plans

### Reconfiguring roles, models, and effort

During `agent-notes install`, wizard step 2 asks you to pick a model per role, and — for models served by a provider with a known effort vocabulary (currently `anthropic`, `openai`) — a follow-up effort prompt, pre-selected to the role's typical effort when that value is valid for the chosen provider. Providers with no effort registry entry (`github-copilot`, `openrouter`, `google`, `moonshot`) skip the effort prompt entirely.

To change these after install:
```bash
agent-notes config role-model [--cli <cli>] <role> <model>    # e.g. role-model worker claude-sonnet-5
agent-notes config role-effort [--cli <cli>] <role> <effort>  # e.g. role-effort worker high
agent-notes config wizard                                     # interactive menu for both
```
`role-effort` validates the effort against the role's currently-assigned model's provider — an invalid value prints that provider's name and its valid effort list. There's no cross-provider mapping: each provider (anthropic, openai) has its own independent effort vocabulary and default.

</details>

---

<details>
<summary>Memory Storage</summary>

Agents accumulate knowledge across sessions. Choose a backend during `agent-notes install`:

**Backends:**
- **`default - Claude Code built-in md files`** (default) — Plain markdown in `~/.claude/agent-memory/<agent>/`. No external tools. Simple, portable.
- **`Obsidian - session`** — Per-project session notes in Obsidian vault. Auto-creates `<vault>/<project>/` with categories: `Patterns/`, `Decisions/`, `Mistakes/`, `Context/`, `Sessions/`. Includes YAML frontmatter and `[[wikilinks]]`.
- **`Obsidian - brain`** — Karpathy's LLM Wiki pattern. Per-project knowledge brain in `<vault>/<project>/raw/` and `wiki/` (sources, concepts, entities, synthesis, sessions). Supports ingest/query/lint operations.
- **`None`** — Disables memory.

**To reconfigure after install:**
```bash
agent-notes install --reconfigure        # switch storage
agent-notes config memory               # interactive backend selector
```

### Local (default)

**Storage:** `~/.claude/agent-memory/<agent>/`

```bash
agent-notes memory list               # list all notes by agent
agent-notes memory show <agent>       # show one agent's notes
agent-notes memory size               # disk usage
agent-notes memory reset [agent]      # clear memory (confirmation required)
agent-notes memory export             # back up to memory-backup/
agent-notes memory import             # restore from memory-backup/
```

### Obsidian (session or brain mode)

**Storage:** `<vault-root>/<project-name>/` (auto-created per CWD)

**Session mode commands:**
```bash
agent-notes memory init               # create folder structure and Index.md
agent-notes memory list               # list all notes (by category or agent)
agent-notes memory vault              # show storage path and init status
agent-notes memory index              # regenerate Index.md
agent-notes memory add <title> <body> [type] [agent]  # type: pattern|decision|mistake|context|session
agent-notes memory reset [agent]      # clear memory (confirmation required)
agent-notes memory export             # back up to memory-backup/
agent-notes memory import             # restore from memory-backup/
```

**Brain mode adds:**
```bash
agent-notes memory ingest <title> <body> <concepts> <entities> <tags>  # manual ingest
agent-notes memory query <question>   # search wiki pages
agent-notes memory lint               # health-check
```

**Setup:** Run `agent-notes install` and choose `Obsidian - session` or `Obsidian - brain`. The wizard auto-detects vaults under `~/Documents`, `~/Desktop`, and `~`. Then run `agent-notes memory init`.

</details>

---

<details>
<summary>Skills</summary>

50+ on-demand knowledge modules across Rails, Docker, Kamal, Git, and Process. Run `agent-notes list skills` for the current list, or browse `agent_notes/data/skills/`.

The session context hook auto-generates a skill index from SKILL.md frontmatter at install time, so agents always know what skills are available without loading full skill content. This keeps context overhead low while maintaining skill discoverability.

### Using skills in Claude Code / OpenCode

```
Use the rails-models skill to help with this association
Load the docker-compose skill for multi-service setup
```

### Core skills addressing failure modes

| Failure mode | What goes wrong | Skills that help |
|---|---|---|
| Misalignment | Claude starts building before the problem is resolved | `/grill-me`, `/grilling`, `/grill-with-docs` |
| Vague scope | Work starts without a spec or ticketed breakdown | `/to-spec`, `/to-tickets`, `/wayfinder`, `/triage` |
| Broken code | Claude codes without a feedback loop or evidence trail | `/tdd`, `/diagnosing-bugs` |
| Ball of mud | Architecture drifts; modules grow shallow and tangled | `/improve-codebase-architecture`, `/codebase-design`, `/domain-modeling` |

**Skill descriptions:**

- `/grill-me`, `/grilling` — Interview the user relentlessly until the plan is fully resolved before touching code
- `/grill-with-docs` — Same, but cross-references CONTEXT.md and ADRs and updates them inline
- `/tdd` — RED-GREEN-REFACTOR with tracer-bullet vertical slices; integration-first testing
- `/diagnosing-bugs` — Diagnosis loop for hard bugs and performance regressions (build a feedback loop first)
- `/improve-codebase-architecture` — Scan for deepening opportunities, present a visual HTML report, then grill the chosen one
- `/codebase-design` — Shared vocabulary for designing deep modules and choosing where seams go
- `/domain-modeling` — Pin down ubiquitous language, maintain a CONTEXT.md glossary and ADRs
- `/handoff` — Compact conversation into a handoff document for a fresh agent session
- `/to-spec` — Synthesize the current conversation into a spec and publish it to the issue tracker
- `/to-tickets` — Break a plan/spec into tracer-bullet tickets with declared blocking edges
- `/wayfinder` — Plan work larger than one agent session as a map of investigation tickets
- `/triage` — Move issues and external PRs through a triage state machine into agent-ready briefs
- `/research` — Investigate a question against primary sources and capture findings as Markdown
- `/prototype` — Throwaway prototypes: terminal app for logic or UI variations for visual
- `/setup-agent-tracker` — One-time per-repo setup of the issue tracker, triage labels, and domain doc layout
- `/writing-great-skills` — Reference for writing and editing skills well

</details>

---

<details>
<summary>Configuration</summary>

### CLI Reference

```
agent-notes <command> [options]
```

| Command | Description |
|---------|-------------|
| `install [--local] [--copy] [--reconfigure]` | Interactive wizard or direct install |
| `uninstall [--local \| --global]` | Remove installed components (both scopes by default) |
| `doctor [--local] [--fix]` | Check installation health |
| `info` | Show status and component counts |
| `list [clis\|models\|roles\|agents\|skills\|rules\|all]` | List engine components or installed |
| `set role <role> <model> [--cli <cli>]` | Change model for a role (Phase 10+) |
| `regenerate [--cli <cli>]` | Rebuild files from state.json (Phase 10+) |
| `validate` | Lint source configuration files |
| `memory [add\|init\|vault\|index\|ingest\|query\|lint\|list\|size\|show\|reset\|export\|import] [name]` | Manage agent memory |
| `cost-report` | Show session cost breakdown by agent and model |

### Supported platforms

| Platform | Install target | Config format |
|----------|---------------|---------------|
| **Claude Code** | `~/.claude/` | YAML frontmatter + Markdown prompts |
| **OpenCode** | `~/.config/opencode/` | YAML frontmatter + Markdown prompts |
| **GitHub Copilot** | `~/.github/` | `copilot-instructions.md` |

### Quick usage examples

```bash
# Interactive install (recommended)
agent-notes install

# Direct install (scripted)
agent-notes install --local --copy

# Check health and fix issues
agent-notes doctor --fix

# List agents, models, or skills
agent-notes list agents
agent-notes list models
agent-notes list skills

# Manage agent memory
agent-notes memory list
agent-notes memory add "Rails enum prefix" \
  "Always use _prefix: true to avoid method name collisions" \
  pattern coder

# Check API key configuration
agent-notes config provider openrouter   # prints "configured" or "no key"

# Reconfigure providers
agent-notes config providers

# Show installation status
agent-notes info

# Validate configuration files
agent-notes validate
```

### Role models

Configure which Claude model powers each role. The default uses Opus 4.6 for reasoning, Sonnet 4.6 for execution, Haiku 4.5 for exploration.

```bash
agent-notes set role lead claude-opus-4-20250514
agent-notes set role coder claude-sonnet-4-20250514
agent-notes set role explorer claude-haiku-4-5-20251001
```

### Providers

agent-notes supports multiple API providers for routing requests. Configure providers via:

```bash
agent-notes config providers     # interactive wizard
agent-notes config provider <name>      # check if configured (without exposing key)
```

</details>

---

<details>
<summary>Development</summary>

### Building and testing

Python 3.10+ required. Create an isolated environment and run tests:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # installs runtime deps + pytest
pytest -q
```

The test suite automatically builds `dist/` before collection (via the `pytest_sessionstart` hook in `tests/conftest.py`), so you do not need to run `python -m build` manually before testing.

### Development workflow

**One-time setup (choose one):**

- Inside a venv: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Or expose the CLI globally via pipx (editable): `pipx install -e .`

**Iteration loop:**

1. Edit source in `agent_notes/data/` (skills, rules, agents, etc.) or Python modules
2. Run `agent-notes install` to rebuild `dist/` and reinstall into your Claude config
3. For a clean reset, run `agent-notes uninstall && agent-notes install`
4. Run `agent-notes validate` to lint configuration files
5. Run tests: `pytest -q` (the suite auto-builds `dist/` first via the conftest hook)

**Full local reset (one-liner):**

```bash
pipx uninstall agent-notes && pipx install -e . && agent-notes uninstall && agent-notes install
```

This command swaps any wheel install for an editable one and clears your Claude config. After this, future edits only need `agent-notes install` (or `agent-notes uninstall && agent-notes install` for a clean wipe).

**Profiles:**

By default, `agent-notes install` re-runs the interactive wizard and prompts for an optional profile label. To reinstall non-interactively into the same profile, use `agent-notes install --profile <label>` (e.g. `work` → installs into `~/.claude-work`).

The plugin build scripts (`scripts/build-claude-plugin.sh`, `scripts/build-opencode-plugin.sh`) automatically use `.venv/bin/python` when present, fall back to system `python3`, and honor a `PYTHON=` override.

**Note:** `uv` is used only in the local development and release workflow (see `scripts/release`). It is not required to install or use agent-notes — end users should use `pipx` or `pip` / `venv`.

### Test structure

- `tests/functional/` — Unit tests
- `tests/integration/` — Build output and artifact validation
- `tests/plugins/` — Plugin artifact validation

### Releasing

The release process is automated via `scripts/release`, which runs **exclusively against the project `.venv`** (invoking `.venv/bin/python` directly, never system `python3`). The pre-flight phase aborts with a clear error if `.venv` does not exist or cannot import `agent_notes`, `tomli_w`, `build`, and `twine`.

**Provision the release environment once:**

```bash
pip install -e ".[dev]" twine
```

**Run the release:**

```bash
scripts/release              # Full release: tests, build, PyPI upload, git tag, marketplace bundle
scripts/release --dry-run    # Check-only: tests, build, twine check, smoke install; skip upload
```

The `--dry-run` flag is useful to validate the entire workflow before committing tags and pushing to PyPI.

### Contributing guidelines

When adding new content:

1. **Edit source files** — all changes go in `agent_notes/data/` directory
2. **Rebuild and test** — `agent-notes install` rebuilds `dist/` and reinstalls; `pytest -q` auto-builds first
3. **Validate** — `agent-notes validate` before committing
4. **Keep it generic** — remove app-specific references
5. **Show examples** — include code samples with explanations
6. **Stay modular** — each skill should be independently usable
7. **Stay concise** — agent prompts under 60 lines

(Note: `python -m build` is only needed to produce a release wheel for distribution, not for local development.)

### Architecture

agent-notes is a 4-layer engine (domain / registries / services / commands). All extensible content (CLIs, models, roles, agents, skills, rules) lives in `agent_notes/data/` as YAML — adding a new CLI/model/role is a YAML drop, no Python changes. Context is loaded in tiers: always-loaded (CLAUDE.md, rules, skill catalog), lazy-loaded (full skill content, agent prompts), and pull-based (memory notes).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ADD_CLI.md](docs/ADD_CLI.md), [docs/ADD_MODEL.md](docs/ADD_MODEL.md), [docs/ADD_ROLE.md](docs/ADD_ROLE.md).

</details>

---

## Inspired by

- [Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — The wiki memory backend implements his compile-once, query-forever knowledge pattern with structured page types and three core operations (ingest, query, lint)
- [Matt Pocock's skills repo](https://github.com/mattpocock/skills) — Skill format (SKILL.md per directory), failure-mode table (misalignment, broken code, architectural degradation), and a set of engineering/productivity skills vendored from the upstream repo (tdd, grill-me, grilling, grill-with-docs, diagnosing-bugs, improve-codebase-architecture, codebase-design, domain-modeling, prototype, handoff, research, to-spec, to-tickets, triage, wayfinder, writing-great-skills). Last synced from upstream commit [`391a270`](https://github.com/mattpocock/skills/commit/391a2701dd948f94f56a39f7533f8eea9a859c87) (2026-07-10), reviewed for prompt-injection before import.

## License

MIT
