---
name: improve-codebase-architecture
description: "Find deepening opportunities — modules where the interface is nearly as complex as the implementation. Use when user wants to improve architecture, reduce coupling, make code more testable, or says 'clean up the design'."
group: process
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities** — refactors that turn shallow modules into deep ones. The aim is testability and simpler call sites.

## Key concepts

- **Module** — anything with an interface and an implementation (function, class, package, file).
- **Deep module** — small interface, large implementation. A lot of behaviour behind a simple API.
- **Shallow module** — interface nearly as complex as the implementation. Low leverage.
- **Seam** — where an interface lives; a place behaviour can be altered without editing in place.
- **Deletion test** — imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.

## Process

### 1. Explore

Walk the codebase organically. Note where you experience friction:
- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow** — interface nearly as complex as the implementation?
- Where are pure functions extracted just for testability, but bugs hide in how they're called?
- Which parts are untested, or only testable by mocking internals?

Apply the **deletion test** to anything that looks suspicious.

### 2. Present candidates

Present a numbered list of deepening opportunities. For each:
- **Files** — which files/modules are involved
- **Problem** — why the current architecture causes friction
- **Solution** — plain English description of what would change
- **Benefit** — how tests or call sites would improve

Do NOT propose interfaces yet. Ask the user: "Which of these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, run a grilling session. Walk the design tree — constraints, the shape of the deepened module, what callers look like after, which tests survive.

If the user rejects a candidate with a load-bearing reason, offer to note it in an ADR so future architecture reviews don't re-suggest it.

## Done means

- Each presented candidate has a clear problem statement and solution
- The user has chosen which to pursue (or explicitly passed)
- No code was changed without user direction
