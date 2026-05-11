## Wiki compile

Write compiled pages via the CLI — never write vault files directly:

```bash
agent-notes memory add "<title>" "<body>" <type> wiki-compiler
```

**Page type mapping:**
- Business domain concept → `concepts`
- External tool, library, or service → `entities`

**Confidence levels:**
- **High** — multiple code files found; data model and behavior confirmed from source
- **Medium** — some code found; partial understanding, note gaps in the page
- **Low** — inferred from naming only; do NOT write the page; flag it in your report

**Rule: never write stubs.** Every page must contain real compiled content derived from source code or integration files. Do not write pages that say "Referenced from source" or equivalent placeholders.
