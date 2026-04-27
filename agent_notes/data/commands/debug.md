Investigate and fix the reported bug using the debugging protocol.

Use the debugging-protocol skill:
1. Instrument — add logging to observe actual values (do not guess yet).
2. Gather evidence — run with instrumentation, collect exact error + stack.
3. Form a hypothesis — state it explicitly before changing anything.
4. Fix — apply the minimal change that addresses the root cause.

Remove all instrumentation after the fix. Run the full test suite.
