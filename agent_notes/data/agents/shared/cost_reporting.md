## Cost reporting

At the END of every response, run `agent-notes cost-report` and include the output as a markdown table prefixed with:

**Session cost** (cumulative for the entire conversation):

Render every column the `agent-notes cost-report` CLI emits — `agent(model)`, `in/out/cache`, `time`, `actual`, `vs Claude Opus 4.7` — in that order. Do not split, drop, or rename columns. Preserve the data verbatim.

**On failure or skip — never fabricate.** If `agent-notes cost-report` returns non-zero, errors, or you skip running it, do NOT render a placeholder table or invent rows like `(cost report unavailable — agent-notes cost-report not run)`. Instead, print one plain line under the heading:

`Cost report skipped: <one-line reason>`

If the command ran but produced an error message, print the error verbatim under the heading instead of a table. Fabricating a table when the CLI did not run is a violation.
