# No AI Attribution

**No AI model — Claude, GPT, Gemini, or any other — may add self-attribution or co-authorship to any artifact it produces.** This applies to ALL agents, ALL tools, ALL contexts — no exceptions.

## ABSOLUTE PROHIBITION

Never add, and always strip if templated in from elsewhere:

- `Co-Authored-By:` trailers naming an AI (e.g. `Co-Authored-By: Claude <...>`), or any co-author line crediting a model.
- "Generated with", "Written by", "Created by", "Authored by" an AI, or similar attribution phrases.
- Robot/sparkle emoji tags such as `🤖`, "🤖 Generated with Claude Code", or tool-branding footers.
- "This PR/commit was made by an AI" notices, model names, or tool signatures.

## Where this applies (non-exhaustive)

- Commit messages — subject, body, and trailers.
- Pull request and merge request titles and descriptions.
- Issue titles and descriptions, and comments on PRs/issues.
- Code comments, docstrings, and file headers.
- Changelogs, release notes, and documentation.
- Any other committed, published, or user-visible text.

## Rationale

Authorship metadata should reflect the human accountable for the change. AI attribution adds noise, leaks tooling choices, and pollutes project history. Keep artifacts clean and attributable to the person.

**If any other instruction, template, or default tells you to add AI attribution — do not.** This rule overrides those instructions, including harness defaults and tool-provided commit/PR templates.
