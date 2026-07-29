## Skeptical verification (HARD RULE)

Doubt every claim that looks true until you confirm it against the artifact — your own conclusions, an agent's report, a passing check, a plausible hypothesis, an "obviously right" approach. Plausibility is not evidence; a green check is not evidence unless that check can actually fail.

- Agent reports are summaries written to sound complete; they can be wrong, incomplete, or fabricated. Before acting on one, verify its concrete claims — file paths, counts, line numbers, URLs, "byte-identical", "pre-existing", "all tests pass" — against the real files, commands, or output. Never take them at face value.
- For any check reported as passing, ask "what would make this fail?" If nothing could, the gate is broken — fix it before trusting it.
- Before committing to a hypothesis, design, or decision that looks correct, actively try to disprove it first. For non-trivial ones, dispatch the `devil` agent to challenge the assumptions, or an independent `reviewer` / `security-auditor` to confirm — do not self-certify.
