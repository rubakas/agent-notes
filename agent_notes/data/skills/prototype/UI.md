# UI Prototype

Generate **several radically different UI variations** on a single route, switchable from a floating bottom bar.

If the question is about logic/state → use [LOGIC.md](LOGIC.md).

## When this is the right shape

- "What should this page look like?"
- "I want to see a few options for this dashboard."
- "Try a different layout for the settings screen."

## Two sub-shapes — prefer A

### Sub-shape A — existing page (preferred)
Variants on the same route, gated by `?variant=` URL param. Existing data fetching stays. Default unless there's a specific reason not to.

### Sub-shape B — new page (last resort)
Only when no existing page fits. Throwaway route named obviously as prototype.

## Process

### 1. Pick N variants
Default to **3**. Cap at 5.

### 2. Generate radically different variants
**Structurally different** — different layout, hierarchy, primary affordance. Not just colors. If two drafts are too similar, redo one.

### 3. Wire with a switcher
Single component gated by `?variant=` search param. Keep all existing data fetching above the switcher.

### 4. Build floating switcher bar
Fixed bottom-center with left/right arrows, variant label, keyboard support. Hidden in production builds.

### 5. Hand it over
Surface the URL and variant keys.

### 6. Capture and clean up
Record winner. Delete losers and switcher. Promote winner properly.

## Anti-patterns
- Variants differing only in color/copy — that's a tweak, not a prototype
- Sharing too much code between variants — each should be free to throw out the layout
- Wiring to real mutations — use stubs
- Promoting prototype directly to production — rewrite properly
