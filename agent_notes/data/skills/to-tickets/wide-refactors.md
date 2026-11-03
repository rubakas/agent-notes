# Wide refactors

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change — rename a column, retype a shared symbol — whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**:

- **Expand**: add the new form beside the old so nothing breaks.
- **Migrate**: move the call sites over in batches sized by blast radius (per package, per directory). Each batch is its own ticket blocked by the expand, and CI stays green batch to batch because the old form still exists.
- **Contract**: delete the old form once no caller remains, in a ticket blocked by every migrate batch.
- If even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket — green is promised only there.
