# 010 — Browser-Tester Automation: Tasks

Ticket index for `spec.md`. Paths relative to `agent_notes/` unless start with `tests/` or `/private/tmp/`. Line numbers current as of 2026-10-30.

## Implementation Phase (T01–T04)

- [x] **T01 browser-tester agent definition** (Req 1)

  **Files**: data/agents/agents.yaml, data/agents/browser-tester.md (new)

  **Changes**:
  - **agents.yaml**: Add entry (agents.yaml has no alphabetical order; the entry is at the END of the file, added in commit 7f935ba, tools and description amended later):
    ```yaml
    browser-tester:
      description: "Runs a browser-test request file in the user's Chrome and returns the report to the main session as its final message, writing only a progress file. Dispatched by the chrome-test skill. Use when a chrome-test request-<uuid>.md is ready to execute. Triggers: browser test, chrome-test, run request."
      role: worker
      mode: subagent
      color: cyan
      effort: medium
      claude:
        tools: "ToolSearch, Read, Write, mcp__claude-in-chrome__list_connected_browsers, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__tabs_close_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__find, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__form_input, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__read_console_messages, mcp__claude-in-chrome__read_network_requests, mcp__claude-in-chrome__resize_window"
      opencode:
        exclude: true
      codex:
        exclude: true
    ```
    No wildcard and no `memory:`; see Req 1.
  - **browser-tester.md** (new, no memory section): Prompt covering tool loading, precondition (list_connected_browsers, BLOCKED), tab lifecycle (`tabs_context_mcp` with `createIfEmpty: true`, then `tabs_create_mcp`, then `tabs_close_mcp`), loop (navigate, form_input, javascript_tool read-only, computer, read_page, get_page_text, find, read_console_messages, read_network_requests, resize_window), progress overwrites, the report returned as the final message (Claude Code refuses subagent report files: "Subagents should return findings as text, not write report files. Include this content in your final response instead."), the verdict line `browser-test <uuid>: <passed>/<total> passed, <failed> failed, <blocked> blocked`, untrusted clause, FAIL vs BLOCKED rules, error handling, cleanup.

  **Acceptance**:
  - agents.yaml entry has worker role, opencode/codex backend blocks (exclude: true), the exact explicit tool list, no wildcard, no memory.
  - browser-tester.md covers all required steps with correct tool names. No screenshot paths in report description.
  - `agent-notes validate` 0 errors.
  - `tests/unit/services/test_browser_tester_agent.py` asserts the exact tools list.

  **Verification**: `grep -A 20 "browser-tester:" data/agents/agents.yaml` confirms backend blocks. `test -f data/agents/browser-tester.md && wc -l data/agents/browser-tester.md` confirms file exists and has content.

- [x] **T02 chrome-test skill integration** (Req 2)

  **Files**: data/skills/chrome-test/SKILL.md

  **Changes**: After the end of Leg A (SKILL.md ~line 243, just before "## Leg B" at line 245), add:
  - "Precondition: MCP Tools and Browser Check" section describing ToolSearch + list_connected_browsers call.
  - "Dispatch browser-tester" section with conditional background/foreground (T06-determined), Modes 1 & 2, completion notification (no polling or timeouts).
  - "Operator handoff (fallback)" section (preserved, shortened).
  - Leg B unchanged.
  - Preserve objective-trigger gate wording (decision_chrome_test_objective_gate).

  **Acceptance**:
  - Precondition, dispatch, and fallback sections present. No "wait 5 min" or polling language in agent path. Completion notification mentioned. Modes 1 & 2 described. Objective-trigger wording intact.
  - `agent-notes validate` 0 errors.
  - `grep "polling\|timeout\|wait for report" data/skills/chrome-test/SKILL.md | grep -v fallback | grep -v operator` returns 0 hits (no polling in agent path).

- [x] **T03 lead templates update** (Req 3)

  **Files**: data/agents/shared/pipelines.md (line 6), data/agents/shared/verification.md (lines 39-41)

  **Changes**:
  - **pipelines.md**: Preserve objective-trigger wording. Replace operator relay section with agent dispatch as primary, operator as fallback. No polling/timeout language. Conditional background/foreground on T06.
  - **verification.md**: Same changes.

  **Acceptance**:
  - Both files reference agent dispatch primary, operator fallback. Objective-trigger wording preserved. No polling in agent path. DEFERRED covers both missing agent and missing operator.
  - `agent-notes build` succeeds.
  - `grep -i "polling\|timeout\|wait" data/agents/shared/pipelines.md data/agents/shared/verification.md | grep -v operator | grep -v fallback` returns 0 hits.

- [ ] **T04 Parallel execution and untrusted content** (Req 4, 5)

  **Scope**: Finalize parallel execution requirement and confirm untrusted-content handling.

  **Changes**:
  - **Parallel execution**: spec.md Requirement 4 currently has two conditional branches (if safe / if collision). T06 determines which. Rewrite with chosen branch (single path, not conditional).
  - **Untrusted content**: Verify browser-tester.md prompt includes untrusted-content clause. Clause already stated in Req 5.

  **Acceptance**:
  - Spec Requirement 4 rewritten with chosen branch (A or B) based on T06 results. Untrusted-content clause confirmed in agent prompt.
  - No conditional wording remains in Requirement 4 section after T06.

  **Verification**: `grep -A 10 "Requirement 4" spec.md | head -15` shows single path (no "if safe" / "if collision" alternatives).

## Verification Phase (T06–T05)

- [ ] **T06 Live verification** (Req 6)

  **Setup** (scratchpad, never touch HOME or ~/.claude):
  - HTML page at /private/tmp/[session]/test-server/index.html: button "Change Text" → "Changed" (pass), button "No Change" → no change (fail).
  - Serve: `cd /private/tmp/[session]/test-server && python3 -m http.server 8080`.

  **T06 (a) Prompt test (this session)**:
  - Dispatch general-purpose subagent with browser-tester.md prompt against http://127.0.0.1:8080.
  - Check report-test0001.md: Scenario 1 PASS, Scenario 2 FAIL.

  **T06 (b) Allowlist test** (scratch project, `chmod -R u+w` before cleanup):
  - `claude -p --chrome --agents '<json for browser-tester with exact rendered tools allowlist>'` with prompt dispatching browser-tester.
  - If `claude -p --chrome` fails, record "owner-verify after reinstall".

  **T06 (c) Parallel** (concurrent agents):
  - Two requests on two UUIDs (request-test0001.md, request-test0002.md) dispatched at same time.
  - Verify both reports complete, neither touched other's tab or bus files.

  **Permission determination**:
  - Observe whether background dispatch is blocked by Chrome extension's site-permission prompt.
  - If blocked → write conditional into T02 & T03: dispatch foreground always.
  - If not blocked → write conditional: dispatch background always.

  **Acceptance**:
  - Test page serves on 127.0.0.1:8080 without error.
  - (a) Prompt test: report-test0001.md has PASS for scenario 1, FAIL for scenario 2. Observations match expected.
  - (b) Allowlist test: allowlist allows ToolSearch or agent loads mcp tools without it. If -p --chrome doesn't work, marked for owner.
  - (c) Parallel: both reports complete, no file corruption, neither agent touched other's files.
  - Permission behavior determined; conditional written into spec.md Req 2 & 3.

  **Verification**:
  - `test -f /private/tmp/[session]/test-server/index.html` confirms page exists.
  - `test -f /private/tmp/[session]/test-bus/report-test0001.md && grep "PASS\|FAIL" /private/tmp/[session]/test-bus/report-test0001.md` confirms report format.
  - `test -f /private/tmp/[session]/test-bus/report-test0002.md` confirms parallel completion.

- [x] **T07 Eval prompts, CHANGELOG, docs, agent tests** (All)

  **Files**: tests/skill_evals/prompts.yaml, CHANGELOG.md, README.md, tests/unit/commands/test_count_agents.py

  **Changes**:
  - **prompts.yaml** (chrome-test block, lines 22–46): already has 4 should_trigger + 2 near_miss, so the ≥4 + ≥2 target is met and no prompt needs adding. Update the `expected_behaviour` strings that describe the operator relay (lines 26, 30, 34) to match the agent-dispatch flow.
  - **CHANGELOG.md**: Entry: "spec 010: Browser-tester automation — automated backend for chrome-test via MCP tools, dispatched from main session if tools available, falls back to manual operator."
  - **README.md**: add browser-tester to the agent table (~lines 247-258) and the agent list (~lines 270-279). The docs/ hits for "explorer" are not agent listings; nothing to add there.
  - **test_count_agents.py**: Verify agent count for claude backend includes browser-tester and excludes codex/opencode exclusions.

  **Acceptance**:
  - prompts.yaml still has ≥4 chrome-test should_trigger and ≥2 near_miss; expected_behaviour wording matches the dispatch flow. `tests/skill_evals/test_evals.py` passes.
  - CHANGELOG has spec 010 entry.
  - browser-tester listed in README.md where agents are documented.
  - test_count_agents.py passes; claude agent count includes browser-tester.

  **Verification**:
  - `uv run python -c "import yaml; p=[x for x in yaml.safe_load(open('tests/skill_evals/prompts.yaml')) if x['skill']=='chrome-test']; print(sum(x['category']=='near_miss' for x in p))"` prints ≥2 (the file is a YAML list; the key is `category`).
  - `uv run pytest tests/skill_evals/test_evals.py -q` passes.
  - `grep -i "spec 010\|browser-tester" CHANGELOG.md` confirms entry.
  - `grep -i "browser-tester" README.md` shows presence.
  - `uv run pytest tests/unit/commands/test_count_agents.py -v` passes.

- [ ] **T05 Final validation** (All, after T07)

  **Scope**: Full validation and test suite.

  **Changes**: None (verification only).

  **Checks**:
  - agents.yaml YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('data/agents/agents.yaml'));"` succeeds.
  - browser-tester.md readable markdown.
  - All edits in T01–T04, T07 complete.

  **Acceptance**:
  - `agent-notes validate` reports 0 errors.
  - `agent-notes build` succeeds.
  - `uv run pytest -q` passes on Python 3.14 and 3.11 (or note known failures).
  - No regressions in existing skills or agents.
  - Agent count test passes.

  **Verification**:
  - `agent-notes validate` produces clean output.
  - `agent-notes build && echo "build OK"`.
  - `uv run pytest tests/unit/commands/test_count_agents.py -v` passes.
  - `uv run pytest tests/ -x -q` shows green.

## Blocking Dependencies

- T01 → T02: T02 needs agent defined.
- T02 → T03: T03 references dispatch pattern from T02.
- T04 depends on T06: T06 results determine parallel/permission conditional.
- T06 (c) parallel test may run in parallel with T01–T04 implementation.
- T06 → T04: T06 findings finalize T04 conditionals.
- T01–T06 → T07: docs/prompts/tests updated after code final.
- T07 → T05: final validation after all changes.

**Execution order**: T01 → T02 → T03 → T04 (draft both conditionals) | T06 (live test in parallel) | T04 finalized (T06 results) | T07 (docs, prompts, tests) | T05 (final validation).
