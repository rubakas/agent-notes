# Fallback: manual operator

Use when the chrome tools are missing (OpenCode, Chrome integration off), no browser is connected, or an extension-failure BLOCKED report came back. An operator must start `claude --chrome` (the dev session cannot launch it; it needs the real, visible Chrome); confirm Chrome and the extension are set up first.

Print numbered operator instructions in chat (real resolved absolute path and real 8-char uuid — no `<uuid>` tokens or shell variables):

```
Browser test ready (a1b2c3d4). To run it:
1. Open a new terminal tab:  claude --chrome
2. Paste: Read and execute the browser test at /Users/alice/.claude-work/chrome-test/myapp-9f86d081884c/request-a1b2c3d4.md
3. When it finishes, say "report a1b2c3d4 ready" here.
```

The chrome session writes `report-<uuid>.md` and `progress-<uuid>.md` itself. When the operator says "report `<uuid>` ready" (or a background or scheduled check, not a blocking loop, sees the file), read `report-<uuid>.md` directly from the bus — no paste-back — and run Leg B. If no operator is available either, the result is DEFERRED (see Precondition).
