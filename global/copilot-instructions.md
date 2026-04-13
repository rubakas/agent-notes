# Global Copilot Instructions

## Code generation

- Read existing code before generating new patterns. Match project conventions.
- Separate business logic from framework concerns.
- Guard clauses and early returns over deep nesting.
- Small focused methods. One responsibility per method.
- Meaningful variable and method names that describe purpose.

## Quality

- No over-engineering: no extra features or abstractions beyond what's needed.
- No comments for obvious code. Comment the "why", not the "what".
- Validate at system boundaries. Trust internal code.

## Testing

- Follow the project's existing test framework and conventions.
- One concept per test with a clear name.
- Happy path + edge cases + error cases.
- Use factories/fixtures over raw data setup when available.

## Safety

- Never include secrets, API keys, or credentials in generated code.
- Never suggest `--force` or `--no-verify` without explicit request.
