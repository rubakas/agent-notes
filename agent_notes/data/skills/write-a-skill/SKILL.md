---
name: write-a-skill
description: "Create new agent skills with proper structure, progressive disclosure, and bundled resources. Use when user wants to create, write, or build a new skill."
group: process
---

# Write a Skill

## Process

1. **Gather requirements** — ask about:
   - What task/domain does the skill cover?
   - What use cases should it handle?
   - Does it need scripts or just instructions?
   - Any reference materials?

2. **Draft the skill** — create:
   - SKILL.md with concise instructions
   - Additional reference files if content exceeds 500 lines
   - Utility scripts if deterministic operations needed

3. **Review with user** — present draft and iterate

## Skill Structure

```
skill-name/
├── SKILL.md           # Main instructions (required)
├── REFERENCE.md       # Detailed docs (if needed)
├── EXAMPLES.md        # Usage examples (if needed)
└── scripts/           # Utility scripts (if needed)
```

## SKILL.md Format

```md
---
name: skill-name
description: "Brief description. Use when [specific triggers]."
group: process | domain
argument-hint: "optional hint"
---

# Skill Name

[Concise instructions, under 100 lines]
```

## Description Requirements

The description is the only thing the agent sees when deciding which skill to load:
1. First sentence: what capability this provides
2. Second sentence: "Use when [specific triggers]"

Max 1024 chars.

## When to Add Scripts
- Deterministic operations (validation, formatting)
- Same code generated repeatedly
- Errors need explicit handling

## When to Split Files
- SKILL.md exceeds 100 lines
- Content has distinct domains
- Advanced features rarely needed

## Review Checklist
- [ ] Description includes triggers
- [ ] SKILL.md under 100 lines (split if longer)
- [ ] group field is set (process or domain)
- [ ] No time-sensitive info
- [ ] Consistent terminology
