---
name: rsi
description: Runs a loop that improves existing code (bugs, performance, consistency, tests, DRY) without adding features. Use when the user says 'rsi', or asks to improve, clean up or harden a codebase. For one refactor use refactoring-protocol.
group: process
disable-model-invocation: true
argument-hint: "[path or scope, optional]"
---

# RSI — Recursive Self-Improvement (Code)

Iteratively improve existing code until it stops yielding improvements. The main session orchestrates; specialized agents do the work. This is a quality loop, not a feature loop.

## Prime invariant

- **Behaviour-preserving except for defect fixes, each in its own commit with a regression test.** Never add functionality, new features, new public API, or new config. A change that adds capability is out of scope: reject it.
- **Tests green before a pass and after every change.** If the target has no test coverage, write a characterization test first, then improve.
- **One change = one concern.** Structure OR behavior, never both in the same change.

## The loop (orchestrated by the main session, loop-until-dry)

1. **Scope.** Resolve the target (arg path, or whole project). Identify the test command and confirm the suite is green. If it is red, stop and report — fix the suite before improving. Don't run the loop on code that lacks meaningful test coverage — write characterization tests first. Ask the user once, before the first change: "Commit each step as I go?" Yes → commit each step locally; No → leave the changes uncommitted and list them in the report. Never push.
2. **Scan — one dimension at a time.** Scan inline when the scope is a few files; dispatch scanners only for scopes a handful of tool calls can't cover, at most 3 at once. Scanners are read-only and produce a ranked list of concrete opportunities:
   - `reviewer` / `security-auditor` → bugs, correctness, vulnerabilities
   - `performance-profiler` → hot paths, N+1, redundant work
   - `system-auditor` → duplication, dead code, coupling, inconsistent implementations of one concept
   - `reviewer` → readability, naming, pattern & consistency adherence
   - `explorer` / `reviewer` → coverage gaps

   Each opportunity is a **finding record**: `file` · `line` · `dimension` · `severity` (blocker | major | minor) · `why` · `fix` (one-line proposed change). When a downstream agent consumes the scan, emit findings as JSON objects with exactly those keys; otherwise the dashed form `file:line — dimension/severity — why — fix` is fine.

3. **Prioritize.** Order: correctness/safety > missing tests on touched code > DRY/duplication > consistency/homogeneity > pattern & convention fit > performance > clarity/naming. Drop anything that changes behavior or adds capability.
4. **Apply one atomic, independent change.** Dispatch `coder` (bugfix) or `refactorer` (behavior-preserving cleanup). Smallest viable diff. Tell the agent not to commit; the main session commits. Sub-agents don't inherit skills, so paste into each brief: the finding record, the prime invariant, the fail-first rule and, for `reviewer` or `refactorer`, the content of `code-review/SMELLS.md` (sibling skill directory).
5. **Verify.** Run affected tests — must stay green. After a batch of atomic changes, `reviewer` confirms: no behavior change, fits conventions, genuinely improves the dimension; mechanical changes rely on green tests. On regression → revert and re-plan. Escalate real logic bugs to `debugger` rather than re-looping.
6. **Commit (only if the user said yes at the start).** One concern per commit, independent and revertable. Use the `git` skill's message format. If the user said no, leave the change uncommitted. Then take the next opportunity.
7. **Repeat passes.** Stop after two consecutive dry passes or 5 passes total, whichever comes first. Then report.

## Dimensions rubric

Each dimension: what to **hunt**, what to **fix**, what to **leave alone**.

- **Bugs & correctness** — off-by-one, nil/None, races, missing error handling, unhandled edge cases. Fix minimally + add a regression test. Don't redesign.
- **Performance** — measured hot paths, N+1 queries, redundant work, bad complexity, unbounded growth. Don't micro-optimize cold paths or trade clarity for guesswork.
- **Code quality** — the smells in `code-review/SMELLS.md` (sibling skill directory), plus deep nesting and magic values. Extract, apply guard clauses, rename. Don't gold-plate.
- **Consistency / homogeneity** — the same kind of thing implemented multiple different ways: mixed styles for one object type, divergent shapes for one concept, inconsistent signatures or return types. Converge on one canonical form and reduce needless variation. Distinct from DRY — this targets divergent *expression* of one concept, not duplicated *logic*. Don't force genuinely different things into a false-common shape.
- **Pattern adherence** — match the project's dominant idioms, structure, and conventions. Align outliers. Don't invent new patterns.
- **Tests** — cover changed or risky code, fix flaky/slow tests, add missing edge cases. Don't test trivial getters.
- **Atomicity** — split god-functions and god-classes into single-responsibility units. Don't over-fragment.
- **Independence** — reduce coupling, remove hidden global state, narrow interfaces. Don't add abstraction layers nobody needs.
- **DRY** — collapse genuine duplication into one source of truth. Don't DRY accidental similarity (premature abstraction is worse than duplication).
- **Dead code** — unused functions, variables, imports, branches. Delete after confirming no external use.

## Gates (hard)

- **No-redesign gate.** If the change needs a module or interface redesign, stop and suggest the user run `/improve-codebase-architecture`.
- **Revert on regression.** On regression, if the change was committed, revert it with `git revert`; if it is uncommitted, discard that one change instead. Never `reset --hard` or force-push.
- **Max 2 review rounds per batch,** then accept or drop the change.
- **Fail-first, anti-gaming.** Every regression test must be shown to FAIL on the unfixed code (it must actually reproduce the bug) BEFORE the fix lands; a characterization test must pass on current code and fail when the pinned behaviour is mutated. Reject any "fix" that games the test rather than addressing root cause — hardcoded expected values, weakened/removed assertions, special-casing the asserted inputs, or operator/equality overloading. A test that passes regardless of the fix proves nothing. The reviewer confirms the test genuinely falsifies the bug.

## Done

Report: improvements grouped by dimension, commits made (or the uncommitted changes, if the user said no), tests added, deferrals (with reasons), and anything skipped as out-of-scope (new functionality).
