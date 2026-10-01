# 003 — Remove Stale Credential-Guard Workarounds

**Feature Branch**: `fix/30-remove-stale-guard-workarounds`

**Created**: 2026-09-22

**Status**: Implemented (PR #45)

**Input**: User description: "Issue #30 — "Reinstall from branch to clear the stale guard, then remove two workarounds" in repo /Users/en3e/code/rubakas/agent-notes (branch: develop, version 2.34.0).

BACKGROUND
Epic #17 left behind two deliberate workarounds because the PreToolUse credential guard running inside Claude Code sessions was the OLD installed agent-notes package, not the working branch. Issue #27 fixed the guard's false positives, but the fix only took effect after a reinstall. That precondition is NOW SATISFIED — see verification below. The two workarounds are still in the tree and should be removed.

SCOPE — remove exactly two pieces of debt. This is a deletion-only change. Do NOT add features, do NOT refactor adjacent code.

WORK ITEM 1 — delete the orphaned test module and its suppression.
- tests/conftest.py lines 14-17 contain:
    # (comment referencing deleted wiki package functionality)
    collect_ignore = [
        "unit/services/test_credential_filter.py",
    ]
- tests/unit/services/test_credential_filter.py still exists on disk. Its only agent_notes import is `from agent_notes.services.wiki_backend import _is_credential_file` (line 3).
- VERIFIED: agent_notes/services/wiki_backend.py does not exist anywhere in the repo. `_is_credential_file` does not exist anywhere in the repo — the sole occurrence of that identifier is inside the orphaned test file itself. The wiki backend was deleted by issue #23 / PR #31.
- VERIFIED: coverage is not lost. tests/unit/commands/test_guard_credentials.py exercises the live replacements (`evaluate_credential_access`, `_is_credential_path`, `_bash_reads_credential`, `_keyword_in_segment`). Its TestIsCredentialPath class duplicates every case from the orphaned file 1:1 (dotenv variants, .pem/.key/.p12/.pfx/.jks, credentials.json/toml/yaml, secrets.*, *-secrets.*, .keystore/.truststore, service-account*.json) and adds keyword-segment matching the old test never had.
- ACTION: delete tests/unit/services/test_credential_filter.py, and delete the collect_ignore block (and its now-pointless comment) from tests/conftest.py. If collect_ignore becomes an empty list, remove the variable entirely rather than leaving `collect_ignore = []`.

WORK ITEM 2 — remove the dead TOML import fallback.
- agent_notes/services/credentials.py lines 14-22 contain a conditional import: `try: import tomllib` / `except ImportError:` falling back to `import tomli as tomllib`, else raising ImportError with the message that tomli is required on Python < 3.11.
- VERIFIED: pyproject.toml line 12 declares `requires-python = ">=3.11"`. tomllib is stdlib from 3.11 onward, so the entire except branch is unreachable.
- ACTION: collapse it to a plain `import tomllib`.
- CONSTRAINT: this file handles credentials. Do not read, print, log or otherwise surface any credential VALUE. The change is purely to import statements. Do not open ~/.agent-notes/credentials.toml or any real secret file. Error messages raised anywhere in this module must never contain a credential value.

PREMISE THAT TURNED OUT FALSE — do not act on it.
Issue #30 implies a `tomli` conditional dependency still needs dropping. VERIFIED FALSE: pyproject.toml line 13 declares `dependencies = ["pyyaml>=6.0", "tomli-w>=1.0.0"]`. `tomli` (the reader) is not a dependency at all. Only `tomli-w` (the writer) is declared, and it is genuinely used. Issue #28 already removed the tomli dependency. Nothing to do here.

OPEN QUESTION FOR THE SPEC TO RESOLVE — RESOLVED 2026-10-01
Five test files replicate the same now-dead try/except tomllib/tomli shim across seven sites: tests/integration/install/test_install_methods.py (lines 25-27 and 37-39), tests/plugins/codex/test_agents.py (7-9), tests/unit/templates/test_codex_frontmatter.py (7-9), tests/unit/cost/test_cost_report.py (9-11), tests/unit/services/test_credentials.py (132-134 and 145-147). Issue #30 does not mention these. RESOLUTION: the owner decided on 2026-10-01 to include them on this branch — the shim is dead for the same reason as in credentials.py (requires-python >=3.11), and leaving five copies behind would carry the same debt into a follow-up for no benefit. They are collapsed to a plain `import tomllib` by a separate commit on this branch.

ACCEPTANCE CRITERIA
- `.venv/bin/python -m pytest` is green. Note pytest is NOT on PATH in this repo; it must be invoked as `.venv/bin/python -m pytest` or via `uv run pytest`. The current baseline is 2196 passing tests; after deleting the orphaned file the count must not drop by more than the tests removed from that file (11 test functions, all parametrized).
- The deleted test file and the collect_ignore entry are both gone; `grep -rn collect_ignore tests/` returns nothing.
- `grep -rn 'import tomli as tomllib' agent_notes/` returns nothing.
- No behavior change in shipped code. `agent-notes build` output must be byte-identical to before the change.
- No AI self-attribution anywhere in commits, code comments, or the PR description. No Co-Authored-By naming a model, no "Generated with" line, no robot emoji. This is a hard project rule.

OUT OF SCOPE
- Reinstalling the user's global CLI (`pipx uninstall agent-notes && pipx install .`). That changes the owner's environment and is their call, not part of this change. Mention it in the spec as a follow-up note only.
- Any change to the credential guard's own logic.
- The Graphify epic (#5-#12) and the plugin epic (#32) — both are being closed as dead/complete."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintainer clears workaround debt left by epic #17 (Priority: P3)

A maintainer of this repo returns to two deliberate workarounds epic #17 left in the tree because the credential guard running in Claude Code sessions was the stale installed package rather than the working branch. Issue #27 fixed the guard and the reinstall precondition is now satisfied, so the maintainer deletes the orphaned test module, its `collect_ignore` suppression, and the dead TOML import fallback, leaving the tree free of debt that no longer has a reason to exist.

**Why this priority**: P3 — pure debt cleanup. No user-facing behavior changes and nothing is blocked on it; it only prevents the next reader from re-deriving why the workarounds were there.

**Independent Test**: Run `uv run pytest -q` and the greps in the acceptance scenarios below; the suite stays green and no reference to the removed code remains.

**Acceptance Scenarios**:

1. **Given** a green baseline of 2196 passing tests, **When** the orphaned test module is deleted, **Then** `uv run pytest -q` passes and the collected-item total drops by exactly the items that file contributed and by no more.
2. **Given** the `collect_ignore` suppression in `tests/conftest.py`, **When** the orphaned module is gone, **Then** `grep -rn collect_ignore tests/` returns no results.
3. **Given** the dead TOML fallback in `agent_notes/services/credentials.py`, **When** it is collapsed, **Then** `grep -rn 'import tomli as tomllib' agent_notes/` returns no results.
4. **Given** the change touches only tests and import statements, **When** `agent-notes build` is run before and after, **Then** its output is byte-identical.
5. **Given** the project's no-AI-attribution rule, **When** the commits and PR description are reviewed, **Then** no AI self-attribution appears anywhere (no Co-Authored-By naming a model, no "Generated with" line, no robot emoji).
6. **Given** the five test files that replicate the dead tomllib/tomli shim across seven sites, **When** the branch is complete, **Then** `git grep -n 'tomli\b' -- . ':!uv.lock' | grep -v 'tomli[-_]w'` returns nothing and the suite still reports 2196 passed, 15 deselected.

### Edge Cases

- The spec attributes test_credential_filter.py to 'workarounds left behind by epic #17' (the credential-guard fix), but the actual conftest.py comment says these are 'Files that test deleted wiki package functionality — removed with the wiki backend,' and the file imports `_is_credential_file` from `agent_notes.services.wiki_backend`, a module confirmed not to exist anywhere in the tree. The dead-file's real cause is the wiki-backend removal, not issue #27/epic #17. The spec's causal story should be corrected so reviewers don't assume issue #27's landing is what makes this safe to delete. (high)
- The 'strict subset' claim underpinning the deletion is unverifiable by execution and structurally doubtful: test_credential_filter.py exercises `_is_credential_file()` in the now-deleted wiki_backend.py, while TestIsCredentialPath exercises a differently-named function `_is_credential_path()` in agent_notes/commands/hook.py — a different module with materially richer rules (template exemptions like .example/.sample/.template/.dist, source-extension exemption for .py, directory-keyword-vs-source-file interplay) that the simpler wiki filter's tests never touch. Because the wiki_backend module is gone, the old file can't be run to produce a live behavioral diff — only a manual/static comparison is possible, and the spec never names who performs it or what to do if a real gap is found. (high)
- Acceptance criterion 'total test count drops by exactly the 11 parametrized functions removed ... and by no more' conflates function count with pytest's collected-item count. Counting the @pytest.mark.parametrize-decorated functions in test_credential_filter.py gives 11, but the actual number of test cases pytest collects and reports in its summary is 39 (4+5+2+5+2+3+3+2+5+4+4 across the parametrize lists). As literally worded, the gate is ambiguous and will not match pytest's own printed total if read as '11 fewer tests', causing a correct deletion to appear to fail the acceptance check. (high)
- 'No AI self-attribution appears in any commit, code comment, or PR description' is listed alongside three grep-based, machine-checkable criteria but has no defined verification command or process (unlike the other three, which all specify an exact grep invocation), making it unenforceable as a gate rather than a policy reminder. (medium)
- 'agent-notes build output is byte-identical before and after the change' has no concrete verification procedure even after enrichment (the enrichment item only asks to 'specify how', it doesn't answer it). tests/conftest.py's pytest_sessionstart shells out to `agent-notes build` and pins XDG_CACHE_HOME per session, so output determinism across separate before/after runs (clean env, working directory, mtimes) is not established as a baseline anyone can diff against. (medium)
- The claim that other files still carry the tomllib/tomli fallback is asserted without an accompanying verification step (verified since: five test files, seven sites), and `tomli` is not declared anywhere in pyproject.toml (only `tomli-w`, used for writing, is a dependency) — meaning the fallback branch in all six affected files may already be dead/untested in every CI environment (CI only runs Python 3.11/3.13, where the primary `import tomllib` always succeeds). This undercuts the enrichment question of whether `tomli` should 'remain a declared dependency,' since it was seemingly never one, and should be resolved before deciding those files are genuinely out of scope. Resolved 2026-10-01: they are in scope and the shim is removed from all of them. (medium)
- The credentials.py tomllib/tomli block being collapsed (lines 14-22) is more than the two-branch shape the spec describes: it includes a nested except that raises a custom ImportError with an install hint ('tomli is required on Python < 3.11...'). Collapsing to a bare `import tomllib` silently drops that friendlier error message in favor of Python's default ModuleNotFoundError; low-risk given the >=3.11 requirement, but the spec should acknowledge this is an intentional, not incidental, behavior change to error messaging on unsupported interpreters. (low)
- The enrichment item asking whether tests/unit/services/ should be deleted if it becomes empty is moot: the directory already contains 30+ other test files (test_skill_filtering.py, test_credentials.py, test_installer_credential_guard.py, etc.), so the answer is trivially 'no' and didn't require enrichment — suggesting the enrichment pass didn't check actual repo state, which should lower confidence in its other unverified claims (the '11 functions' count, the file count for the tomli shim — six claimed, five actual, the 'strict subset' claim). (low)
- Two enrichment items are in tension with no reconciliation: one says to verify the strict-subset claim and 'note what happens if a gap is found,' implying a missing test case might need porting into test_guard_credentials.py; the rollback note says 'if pytest fails after either deletion, revert that specific change rather than debugging forward.' A genuine coverage gap wouldn't necessarily manifest as a pytest failure (no test currently encodes the missing behavior), so reverting wouldn't surface or fix it, and the spec gives no guidance on which path to take. (medium)
- The acceptance criterion 'test count drops by exactly 11' is a brittle, count-based proxy for equivalence rather than a semantic check that every removed assertion/parametrize case is genuinely duplicated elsewhere. A count match can pass while a specific adversarial-input edge case (e.g., a path-traversal or unusual credential filename variant) that was only exercised by the deleted file is silently lost from coverage. (medium)
- No requirement for a second reviewer or security-aware sign-off specifically on the diff touching credentials.py, despite the module's own docstring flagging it as security-critical. Even for a 'mechanical' import collapse, a second pair of eyes reduces risk of subtle regressions in a file that handles secret values. (low)
- The enrichment item to check other uses of collect_ignore doesn't specify what action to take if it's found referenced by CI config or plugins beyond conftest.py — there's no fallback plan if removal changes pytest collection/exit behavior in CI in an unexpected way. (low)
- The instruction to avoid printing credential-like fixture contents during diff/patch review doesn't extend to CI log output more broadly — e.g., pytest_sessionstart in conftest.py captures and prints full stdout/stderr from a subprocess build on failure, which could echo secret-like values if a real ~/.agent-notes/credentials.toml exists in the environment where this change is tested. (low)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST delete `tests/unit/services/test_credential_filter.py`; its sole assertions are already a strict subset of `tests/unit/commands/test_guard_credentials.py::TestIsCredentialPath`.
- **FR-002**: System MUST remove the `collect_ignore` block and its now-pointless comment from `tests/conftest.py` (lines 14-17); if the list becomes empty, delete the variable entirely rather than leaving `collect_ignore = []`.
- **FR-003**: System MUST collapse the `try: import tomllib / except ImportError: import tomli as tomllib` fallback in `agent_notes/services/credentials.py` (lines 14-22) to a plain `import tomllib`, since `pyproject.toml` requires Python >=3.11 where `tomllib` is stdlib.
- **FR-004**: System MUST also collapse the same dead tomllib/tomli shim in the five other test files (seven sites) to a plain `import tomllib`. The owner decided on 2026-10-01 to include them on this branch rather than defer: the shim is dead for exactly the same reason as in `credentials.py`, and the change is import-only with no effect on test outcomes.
- **FR-005**: System MUST make no changes to the credential guard's own logic, and do not read, log, or surface any credential value while editing `credentials.py`.
- **FR-006**: System MUST do not reinstall the global CLI (`pipx uninstall/install`) as part of this change; note it only as a follow-up for the repo owner.
- **FR-007**: System MUST address blocking security finding: The spec's justification for deleting tests/unit/services/test_credential_filter.py is factually inconsistent with the code: the file imports _is_credential_file from agent_notes.services.wiki_backend, a module that no longer exists (conftest.py's own comment says it was 'removed with the wiki backend'), not from an epic #17/issue #27 credential-guard workaround. This means the required 'strict subset' comparison is between two independently-implemented, unrelated credential-detection functions (a deleted wiki-export exclusion filter vs. the live CLI guard's _is_credential_path). The subset claim must be verified by an actual diff of parametrize cases/expected outputs against the current test_guard_credentials.py, not accepted on the issue's narrative, before the file is deleted. [severity: medium]
- **FR-008**: System MUST address blocking security finding: credentials.py is explicitly marked CRITICAL in its own docstring (must never log/print/expose secret values), yet the spec does not require confirming the failure mode after collapsing the tomllib/tomli try/except to a bare 'import tomllib'. If the CLI is ever invoked under an unsupported Python (<3.11) or a broken venv despite pyproject's constraint, the resulting unguarded ImportError's behavior (hard crash = fail-closed/safe, vs. caught/swallowed upstream = fail-open/unsafe, silently disabling the credential guard or credential store) is not verified anywhere in the requirements or acceptance criteria. [severity: high]
- **FR-009**: System MUST address blocking security finding: Verifying that the CI workflow matrix doesn't still run tests against Python <3.11 is listed only as an enrichment 'check' item, not as a hard, gating acceptance criterion. If any supported environment still runs <3.11, removing the fallback breaks the only working import path for the credential-storage module in that environment; this must be a verified precondition before merge, not an optional note. [severity: medium]

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The test suite reports 2196 passed, 15 deselected after the tomli shim removal — unchanged from the baseline, because the change is import-only.
- **SC-002**: No reference to the removed code remains: `grep -rn collect_ignore tests/` is empty, and `git grep -n 'tomli\b' -- . ':!uv.lock' | grep -v 'tomli[-_]w'` is empty.
- **SC-003**: Shipped behavior is unchanged — `agent-notes build` output is byte-identical before and after.

## Assumptions

- The repo's `requires-python = ">=3.11"` is authoritative and CI runs only 3.11+, so `tomllib` is always importable from the stdlib and every `tomli` fallback branch is unreachable.
- `tomli` (the reader) is not and never was a declared dependency; only `tomli-w` (the writer) is, and it stays.
- The credential-guard reinstall precondition from issue #27 is satisfied — see Verification below.
- This is a deletion-only change: no features, no refactors of adjacent code.

## Verification

The credential guard was re-checked against the issue #27 cases on both the installed 2.33.1 and the source 2.34.0, with no divergence between versions. Template files (`.env.example`, `.env.sample`, `.env.dist`, `config.template`) and `.py` sources are allowed; `.env`, `.env.production`, the user credential store, `server.pem`, and `cat .env` are denied. Known non-goal, already documented in #27: a credential filename mentioned in prose inside a Bash command is still denied.
