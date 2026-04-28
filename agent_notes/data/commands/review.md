Review the current changes for correctness, safety, clarity, and consistency.

Use the code-review skill:
1. Run: git diff HEAD (or git diff --staged if reviewing staged changes).
2. Work through the four review lenses: correctness → safety → clarity → consistency.
3. Report BLOCKING findings and SUGGESTIONS separately.
4. If security-sensitive code is changed (auth, input handling, data access),
   apply security-auditor scrutiny.

Do not suggest cosmetic changes unless they create real ambiguity.
