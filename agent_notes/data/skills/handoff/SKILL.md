---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
group: process
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Create a fresh directory with `mktemp -d` and save the document there - not in the current workspace. Print the document's absolute path to the user.

Use this skeleton, keeping each section short:

```markdown
# Handoff: <topic>

## Goal
<what the next session is for>

## State
<what is done and what is half-done>

## Next steps
<ordered, concrete>

## References
<paths and URLs of specs, plans, ADRs, issues, commits>

## Suggested skills
<skills the next agent should invoke>

## Open questions
<what still needs a decision>
```

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
