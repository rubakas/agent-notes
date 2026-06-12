---
name: rsi
description: "Recursive code-improvement loop: iteratively harden an existing codebase across bugs, performance, quality, consistency/homogeneity, pattern adherence, tests, atomicity, independence, and DRY — strictly without adding functionality. Use when the user wants to improve, clean up, or harden existing code, says 'rsi', or asks to raise code quality without new features. For a single one-shot refactor use refactoring-protocol; for module or interface redesign use improve-codebase-architecture."
group: process
argument-hint: "[path or scope, optional]"
---

# RSI — Recursive Self-Improvement (Code)

Iteratively improve EXISTING code until it stops yielding improvements. The lead orchestrates; specialized agents do the work. This is a quality loop, not a feature loop.

## Prime invariant

- **Behavior-preserving.** NEVER add functionality, new features, new public API, or new config. Only improve what already exists.
- **Tests green before a pass and after every change.** If the target has no test coverage, write a characterization test FIRST, then improve.
- **One change = one concern.** Structure OR behavior, never both in the same change.

## The loop (lead-orchestrated, loop-until-dry)

1. **Scope.** Resolve the target (arg path, or whole project). Identify the test command and confirm the suite is green. If it is red, stop and report — fix the suite before improving.
2. **Scan — one dimension at a time.** Dispatch read-only agents to produce a ranked list of concrete opportunities:
   - `debugger` / `security-auditor` → bugs, correctness, vulnerabilities
   - `performance-profiler` → hot paths, N+1, redundant work
   - `system-auditor` → duplication, dead code, coupling, inconsistent implementations of one concept
   - `reviewer` → readability, naming, pattern & consistency adherence
   - `test-writer` (read-only pass) → coverage gaps

   Each opportunity is a **finding record**: `file` · `line` · `dimension` · `severity` (blocker | major | minor) · `why` · `fix` (one-line proposed change). When a downstream agent consumes the scan, emit findings as JSON objects with exactly those keys; otherwise the dashed form `file:line — dimension/severity — why — fix` is fine.

3. **Prioritize.** Order: correctness/safety > missing tests on touched code > DRY/duplication > consistency/homogeneity > pattern & convention fit > performance > clarity/naming. Drop anything that changes behavior or adds capability.
4. **Apply ONE atomic, independent change.** Dispatch `coder` (bugfix) or `refactorer` (behavior-preserving cleanup). Smallest viable diff.
5. **Verify.** Run affected tests — must stay green. `reviewer` confirms: no behavior change, fits conventions, genuinely improves the dimension. On regression → revert and re-plan.
6. **Commit (auto, atomic).** One concern per commit, independent and revertable. Use the `git` skill's message format. Then take the next opportunity.
7. **Repeat passes.** Converge when TWO consecutive full passes surface no new actionable improvement. Then report.

## Dimensions rubric

Each dimension: what to **hunt**, what to **fix**, what to **leave alone**.

- **Bugs & correctness** — off-by-one, nil/None, races, missing error handling, unhandled edge cases. Fix minimally + add a regression test. Don't redesign.
- **Performance** — measured hot paths, N+1 queries, redundant work, bad complexity, unbounded growth. Don't micro-optimize cold paths or trade clarity for guesswork.
- **Code quality** — long methods, deep nesting, unclear names, magic values. Extract, apply guard clauses, rename. Don't gold-plate.
- **Consistency / homogeneity** — the same kind of thing implemented multiple different ways: mixed styles for one object type, divergent shapes for one concept, inconsistent signatures or return types. Converge on one canonical form and reduce needless variation. Distinct from DRY — this targets divergent *expression* of one concept, not duplicated *logic*. Don't force genuinely different things into a false-common shape.
- **Pattern adherence** — match the project's dominant idioms, structure, and conventions. Align outliers. Don't invent new patterns.
- **Tests** — cover changed or risky code, fix flaky/slow tests, add missing edge cases. Don't test trivial getters.
- **Atomicity** — split god-functions and god-classes into single-responsibility units. Don't over-fragment.
- **Independence** — reduce coupling, remove hidden global state, narrow interfaces. Don't add abstraction layers nobody needs.
- **DRY** — collapse genuine duplication into one source of truth. Don't DRY accidental similarity (premature abstraction is worse than duplication).
- **Dead code** — unused functions, variables, imports, branches. Delete after confirming no external use.

## Gates (hard)

- **Green-before / green-after.** A red suite halts the loop.
- **No-feature gate.** If a change adds capability, it is out of scope — reject it.
- **Atomic & independent commits.** Revert on regression with `git revert` — never `reset --hard` or force-push.
- **Max 2 review rounds per change,** then accept or drop it.

## Done

Report: improvements grouped by dimension, commits made, tests added, deferrals (with reasons), and anything skipped as out-of-scope (new functionality).
