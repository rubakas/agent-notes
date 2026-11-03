# Skill review rubric (2026-11-03)

These sources were re-fetched on 2026-11-03:

| Key | Source |
|---|---|
| BP | https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices |
| CC | https://code.claude.com/docs/en/skills |
| AS | https://agentskills.io/specification |
| PB | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices |
| O5 | the Opus 5 / 5.5 prompting pages under that path |
| S55 | the Sonnet 5.5 prompting page |
| F51 | the Fable 5.1 prompting page |

Project facts:
- The source skills live in `agent_notes/data/skills/<name>/`.
- They are installed as identical files to Claude Code (`~/.claude/skills/`) and OpenCode. Codex and Copilot get no skills.
- Our validator is `agent_notes/services/skill_validation.py`.

Score each skill on G1–G3, W1–W6, S1–S7, E1–E5 and A1–A6, giving each item **pass**, **minor** or **fail** with `file:line` evidence.

## G — Goal and discovery

- **G1 (BP, CC).** The description says, in the third person, both what the skill does and when to use it ("Use when …"). It contains the specific trigger terms a user would type, and puts the key use case first.
  - Vague phrasing such as "helps with", "hardening" or "wants X" fails.
- **G2 (BP).** After reading the body once, an LLM can state the goal, the inputs, the output or deliverable, and the stop condition in one sentence each.
  - Write those four sentences yourself, as the model would. If you cannot, that is a fail.
- **G3 (CC).** The invocation mode fits the skill:
  - A skill with side effects or an expensive fan-out, run by hand → `disable-model-invocation: true`.
  - A reference-only skill → consider `user-invocable: false`.
  - A skill that takes an argument → `argument-hint`.
  - Its triggers must not collide with another skill's or with an agent's (list any overlaps by name).

## W — Wording

- **W1 (PB, O5).** No emphatic or over-prompting language outside true safety rules: CRITICAL, MUST, NEVER, ALWAYS and IMPORTANT in caps, "if in doubt", or "you have no choice". Safety rules that stay emphatic are credentials, destructive actions, no AI attribution and test integrity.
- **W2 (PB, O5).** No anti-laziness or over-verification filler, such as "be thorough", "be aggressive", "refuse to give up", "double-check", or "verify again" without a concrete check.
- **W3 (BP).** Terminology stays consistent: one term per concept across SKILL.md and its references.
- **W4 (BP).** No time-sensitive statements, or they sit in an "old patterns" section.
- **W5 (BP).** It gives a default plus an escape hatch, not a menu of options.
- **W6 (O5, S55, F51).** Scope discipline:
  - it doesn't tell the model to add tests, docs or features the user didn't ask for;
  - it doesn't ask "Want me to…?" mid-task when the work is already authorised;
  - its subagent use fits "delegate only large independent work; keep spawn counts low; don't use subagents to verify your own work".

## S — Structure

- **S1 (BP, AS).** The SKILL.md body is under 500 lines and under 5,000 tokens (bytes / 3.5). Report both numbers.
- **S2 (BP).** Every reference file links directly from SKILL.md, one level deep. No reference file links to another.
- **S3 (BP).** A reference over 100 lines has a `## Contents` list within its first 20 lines.
- **S4 (BP).** A complex multistep workflow has numbered steps, a copyable checklist where steps can be skipped, and a feedback loop (validate → fix → repeat) for quality-critical output.
- **S5 (BP).** Each step makes clear whether to run a bundled script or read it as reference.
- **S6 (BP).** Concrete examples (input → output) are given where output quality depends on style. The examples are concrete, not abstract.
- **S7 (BP).** Files have descriptive names and use forward slashes.

## E — Economy: every token earns its place (BP "Claude is already very smart")

- **E1.** No explanations of things Claude already knows: generic definitions, how git works, what a test is.
- **E2.** No duplication inside the skill, or with another skill, rule or agent body. Name the other file and line.
- **E3.** Content needed only in some branches lives in a reference file, not in SKILL.md.
- **E4.** Estimate the bytes that could be cut without loss, and list the cut lines.
- **E5 (CC).** The description plus `when_to_use` fits the listing budget: no padding, and the key use case comes first.

## A — Accuracy: verify every reference; never assume it is right

- **A1.** Every `agent-notes` subcommand and flag the skill names exists.
  - Check: `uv run agent-notes <cmd> --help` in the repo, and the source under `agent_notes/commands/`.
- **A2.** Every `gh`, `glab`, `git` or other CLI flag the skill names exists and does what the skill says.
  - Check: `<tool> <cmd> --help` locally, or the vendor's docs page; cite it.
  - Note any flag whose piped output differs from its TTY output.
- **A3.** Every agent name is real, and its tools match what the skill asks it to do.
  - Real agents: `agent_notes/data/agents/agents.yaml`, plus the Claude Code built-ins general-purpose, Explore and Plan.
  - For example, asking an agent without Bash to run `git diff` is a fail.
  - Spec 011 Req 1d gives these six agents exactly `Read, Grep, Glob, Bash, WebFetch`: reviewer, security-auditor, system-auditor, database-specialist, performance-profiler and api-reviewer.
- **A4.** Tool names:
  - Claude Code: Agent, SendMessage, Read, Write, Edit, Bash, Grep, Glob, WebFetch, WebSearch, Skill, ToolSearch and AskUserQuestion. MCP tools are named `mcp__<server>__<tool>`.
  - OpenCode: task, todowrite and similar.
  - The skill must work on both backends, or say which one each name belongs to.
- **A5.** Paths, files, templates and other skills the skill points to exist, and say what the skill claims.
  - Subagents do not inherit skills the main session invoked. A skill that tells a subagent to "use skill X" or "follow X's list" must paste the content into the brief.
- **A6.** Code behaviour the skill describes matches the code: layouts, file formats, defaults. Cite the code `file:line`.

## Severity

- **High:** the model would run a wrong or non-existent command, take a harmful or destructive step, or reach a wrong outcome.
- **Medium:**
  - a likely mis-trigger or confusion;
  - a contradiction;
  - a rule violation from BP or CC;
  - more than 1 KB of avoidable tokens;
  - an agent or tool mismatch.
- **Low:** style, or a small saving.
