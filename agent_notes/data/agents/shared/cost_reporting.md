## Cost reporting

At the END of every response, run `cost-report` and include the output as a markdown table prefixed with:

**Session cost** (cumulative for the entire conversation):

Render every column the `cost-report` CLI emits — `agent(model)`, `in/out/cache`, `time`, `actual`, `vs Claude Opus 4.7` — in that order. Do not split, drop, or rename columns. Strip ANSI color codes; otherwise preserve the data verbatim.
