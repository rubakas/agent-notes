"""Spike: run ONE skill-eval prompt through a real `claude -p` session.

Not collected by pytest (no test_ prefix). Makes a live, billed API call.

    uv run python tests/skill_evals/runner.py --skill git --index 0
    uv run python tests/skill_evals/runner.py --skill git --index 0 --model claude-haiku-4-5

--index is the position among that skill's entries in prompts.yaml
(file order, counting both categories).

What it does: copies agent_notes/data/skills into <tmp>/.claude/skills/ of a
throwaway project, runs claude there, parses the stream-json output for Skill
tool_use events, and judges PASS/FAIL against the entry's category.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SKILLS_DIR = REPO_ROOT / "agent_notes" / "data" / "skills"
PROMPTS_FILE = HERE / "prompts.yaml"

COMMAND_NAME_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


def parse_stream(lines):
    """Parse stream-json lines into {"skills": [...], "usage": {...}, "total_cost_usd": float}.

    A skill counts as loaded when the model calls the Skill tool, or when a user
    turn carries a <command-name> marker (how a slash invocation shows up).
    Names are de-duplicated, first-seen order (the live spike saw "git" twice
    for one prompt). Unparseable lines are skipped. usage/total_cost_usd come from the last
    "result" event and are None if the stream has none.
    """
    skills = []
    usage = None
    total_cost = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "result":
            usage = event.get("usage")
            total_cost = event.get("total_cost_usd")
            continue
        if kind not in ("assistant", "user"):
            continue
        content = (event.get("message") or {}).get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for block in content or []:
            if not isinstance(block, dict):
                continue
            if kind == "assistant" and block.get("type") == "tool_use" and block.get("name") == "Skill":
                name = (block.get("input") or {}).get("skill")
                if name:
                    skills.append(name.lstrip("/"))
            elif kind == "user" and block.get("type") == "text":
                skills.extend(COMMAND_NAME_RE.findall(block.get("text", "")))
    return {"skills": list(dict.fromkeys(skills)), "usage": usage, "total_cost_usd": total_cost}


def judge(category, skill, loaded):
    """should_trigger passes when `skill` loaded; near_miss passes when it did not."""
    return (skill in loaded) == (category == "should_trigger")


def pick_entry(entries, skill, index):
    own = [e for e in entries if e["skill"] == skill]
    if not own:
        raise SystemExit(f"no entries for skill {skill!r}")
    if not 0 <= index < len(own):
        raise SystemExit(f"--index must be 0..{len(own) - 1} for {skill!r}")
    return own[index]


def run_claude(prompt, model, workdir):
    # --tools Skill: the only tool is Skill, so a triggered skill cannot run git,
    #   edit files or hit the network; the test measures routing, not execution.
    # --setting-sources project,local: ignore user-level settings and hooks.
    # --strict-mcp-config (no --mcp-config): no MCP servers, so no tool-list noise.
    # --no-session-persistence: do not write a transcript for this run.
    # --max-budget-usd: hard stop on cost.
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--model", model,
        "--tools", "Skill",
        "--permission-mode", "dontAsk",
        "--allowedTools", "Skill",
        "--setting-sources", "project,local",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--max-budget-usd", "0.50",
    ]
    return subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=300)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skill", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--model", default="claude-haiku-4-5")
    args = ap.parse_args(argv)

    entries = yaml.safe_load(PROMPTS_FILE.read_text())
    entry = pick_entry(entries, args.skill, args.index)

    workdir = Path(tempfile.mkdtemp(prefix="skill-eval-"))
    shutil.copytree(SKILLS_DIR, workdir / ".claude" / "skills")
    try:
        proc = run_claude(entry["prompt"], args.model, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    parsed = parse_stream(proc.stdout.splitlines())
    print(f"skill:    {entry['skill']} ({entry['category']})")
    print(f"model:    {args.model}")
    print(f"prompt:   {entry['prompt']}")
    print(f"loaded:   {parsed['skills'] or '(none)'}")
    print(f"usage:    {json.dumps(parsed['usage'])}")
    print(f"cost_usd: {parsed['total_cost_usd']}")
    if parsed["usage"] is None:
        print(f"ERROR: no result event (exit {proc.returncode}). stderr:\n{proc.stderr}")
        return 2
    ok = judge(entry["category"], entry["skill"], parsed["skills"])
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
