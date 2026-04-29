# PyPI Metadata Audit

## Summary

Three sources hold project metadata: `pyproject.toml`, `agent_notes/VERSION` (canonical version), `.claude-plugin/plugin.json`. Version is single-sourced (`dynamic = ["version"]`), but `plugin.json` duplicates `name`, `description`, `author`, `license`, `keywords`. `pyproject.toml` is missing eight standard PyPI fields (readme, classifiers, keywords, extra URLs). Top recommendation: derive `plugin.json` non-version fields from `pyproject.toml` in `build-plugin.sh`, and expand `pyproject.toml` to a full PyPI manifest.

## Field-by-field

| Field | Canonical source | Duplicates | Status |
|---|---|---|---|
| version | `agent_notes/VERSION` | `.claude-plugin/plugin.json` (synced by `scripts/build-plugin.sh`) | OK — single source |
| name | `pyproject.toml` | `.claude-plugin/plugin.json:2` | Drift risk (manual) |
| description | `pyproject.toml` | `.claude-plugin/plugin.json:4`; README.md tagline | Drift risk (manual) |
| authors | `pyproject.toml` | `.claude-plugin/plugin.json:5-7` | Drift risk (manual) |
| license | `pyproject.toml` | `.claude-plugin/plugin.json:9`; README.md "License" section; `LICENSE` | Drift risk (manual) |
| keywords | `.claude-plugin/plugin.json:10-15` | — | Missing in `pyproject.toml` |
| repository URL | `pyproject.toml` | `.claude-plugin/plugin.json:8`; README links | Drift risk |
| python entry points | `pyproject.toml` (`agent-notes`, `cost-report`) | — | OK |
| dependencies | `pyproject.toml` (`pyyaml>=6.0`) | — | OK |
| `__version__` attr | not defined | `agent_notes/__init__.py` only has docstring | Optional gap |
| README marketing copy | `README.md` | `.claude-plugin/README.md` (different shorter copy) | Intentional split, but no link between them |

`agent_notes/VERSION` contains `2.0.4`. `scripts/release` (lines 86-95, 137-153) writes the new version then runs `scripts/build-plugin.sh` (lines 24-31), which patches `plugin.json["version"]`. No other `plugin.json` field is rewritten. No `setup.py` / `setup.cfg`. `agent_notes/__init__.py` has only a docstring, no `__version__`.

## Missing PyPI fields

`pyproject.toml` lacks fields needed for a polished PyPI page:

- `readme = "README.md"` — without this, PyPI shows no long description (and Markdown won't render).
- `classifiers` — none. Recommend: `Development Status :: 5 - Production/Stable`, `Intended Audience :: Developers`, `License :: OSI Approved :: MIT License`, `Operating System :: OS Independent`, `Programming Language :: Python :: 3` plus `:: 3.9`–`:: 3.12`, `Topic :: Software Development`, `Topic :: Software Development :: Code Generators`, `Environment :: Console`.
- `keywords` — present in `plugin.json`, missing here. Recommend `["agents", "claude", "claude-code", "opencode", "ai", "cli", "agent-orchestration"]`.
- `[project.urls]` — only `Homepage` and `Repository` (identical). Add `Issues`, `Changelog`, optionally `Documentation`.
- `license = "MIT"` is PEP 639 SPDX style; the classifier above is a safer fallback for older indexers.

`dynamic = ["version"]` is correct, no change needed.

## Recommended single-source pattern

1. `pyproject.toml` is the master for: `name`, `description`, `authors`, `license`, `keywords`, `urls`, `classifiers`, `dependencies`, `requires-python`, `readme`.
2. `agent_notes/VERSION` is the master for `version`. `pyproject.toml` reads it via the existing `[tool.setuptools.dynamic]` section. `scripts/build-plugin.sh` writes it into `plugin.json`.
3. Extend `scripts/build-plugin.sh` to also copy `name`, `description`, `keywords`, `author.name`, `license`, and `repository` out of `pyproject.toml` into `plugin.json` so `plugin.json` becomes a fully generated artifact.
4. README content stays human-authored in `README.md`. `.claude-plugin/README.md` stays a separate shorter copy (different audience), but cross-link them.

## Action items

1. Add `readme`, `keywords`, `classifiers`, expanded `[project.urls]` to `pyproject.toml` (no behavior change; pure metadata).
2. Extend `scripts/build-plugin.sh` to derive `plugin.json` non-version fields from `pyproject.toml` (small Python block, same shape as the existing version-write block).
3. After step 2, treat `.claude-plugin/plugin.json` as a build artifact — note in `.gitignore`-adjacent docs that hand-edits will be overwritten on next release.
4. Optional: add `__version__` to `agent_notes/__init__.py` reading from `VERSION` for callers who do `import agent_notes; agent_notes.__version__`.
