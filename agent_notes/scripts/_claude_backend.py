"""Session cost report for Claude Code — reads JSONL transcripts."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from . import _pricing
from ._formatting import (
    fmt_time, render_cost_table,
)
from ..services.state_store import state_file as _state_file, load_state as _load_state


def _resolve_claude_homes() -> list[Path]:
    """Return all configured Claude home directories (deduped, default first)."""
    default = Path.home() / ".claude"
    seen: set[Path] = set()
    homes: list[Path] = []

    def _add(p: Path) -> None:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            homes.append(p)

    _add(default)
    try:
        state = _load_state()
        if state is not None:
            scopes = []
            if state.global_install:
                scopes.append(state.global_install)
            for ss in (state.global_installs or {}).values():
                scopes.append(ss)
            for scope in scopes:
                backend = scope.clis.get("claude")
                if backend and backend.global_home_override:
                    _add(Path(backend.global_home_override).expanduser())
    except Exception:
        pass
    return homes


def _parse_timestamp(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def _last_message_ts(path: Path) -> float:
    last_ts = 0.0
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = obj.get("timestamp")
                if ts:
                    parsed = _parse_timestamp(ts)
                    if parsed:
                        last_ts = parsed
    except OSError:
        pass
    return last_ts or path.stat().st_mtime


def _load_jsonl(path: Path) -> list:
    messages = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages


def _load_configured_models() -> dict[str, str]:
    state_path = _state_file()
    try:
        with state_path.open() as f:
            data = json.load(f)
        global_scope = data.get("global")
        if global_scope:
            role_models = (
                global_scope.get("clis", {})
                .get("claude", {})
                .get("role_models")
            )
            if isinstance(role_models, dict):
                return role_models
        # Global absent or empty — fall back to local scope for cwd
        local_scope = (
            data.get("local", {})
            .get(str(Path.cwd()), {})
            .get("clis", {})
            .get("claude", {})
            .get("role_models")
        )
        if isinstance(local_scope, dict):
            return local_scope
        return {}
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return {}


def _load_subagent_label(meta_path: Path) -> str:
    try:
        with meta_path.open() as f:
            meta = json.load(f)
        return meta.get("agentType", "subagent")
    except Exception:
        return "subagent"


def _ts_to_iso(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_transcript_dir(session_id: str) -> Path | None:
    target = f"{session_id}.jsonl"
    for home in _resolve_claude_homes():
        projects_dir = home / "projects"
        if not projects_dir.exists():
            continue
        for proj_dir in projects_dir.iterdir():
            if proj_dir.is_dir() and (proj_dir / target).exists():
                return proj_dir
    return None


def run(since: float | None = None, session_id: str | None = None) -> int:
    slug = str(Path.cwd().resolve()).replace("/", "-")
    transcript_dir = None
    for home in _resolve_claude_homes():
        candidate = home / "projects" / slug
        if candidate.exists():
            transcript_dir = candidate
            break

    if transcript_dir is None:
        if session_id:
            transcript_dir = _find_transcript_dir(session_id)
        if not transcript_dir or not transcript_dir.exists():
            print("No Claude Code transcript found for this project")
            return 0

    if session_id is not None:
        transcript_file = transcript_dir / f"{session_id}.jsonl"
        if not transcript_file.exists():
            print(f"No transcript found for session {session_id!r} in {transcript_dir}")
            return 1
    else:
        jsonl_files = sorted(transcript_dir.glob("*.jsonl"), key=_last_message_ts)
        if not jsonl_files:
            print(f"No JSONL transcripts found in {transcript_dir}")
            return 0
        transcript_file = jsonl_files[-1]
        session_id = transcript_file.stem

    raw_messages: list = []
    lead_messages = _load_jsonl(transcript_file)

    # Collect per-agent wall-clock time from toolUseResult entries in parent transcript.
    # Each user message with toolUseResult.totalDurationMs records sub-agent wall time.
    agent_time_ms: dict[str, int] = {}
    for obj in lead_messages:
        tool_result = obj.get("toolUseResult")
        if not isinstance(tool_result, dict):
            continue
        duration_ms = tool_result.get("totalDurationMs")
        agent_type = tool_result.get("agentType")
        if duration_ms is not None and agent_type:
            agent_time_ms[agent_type] = agent_time_ms.get(agent_type, 0) + duration_ms

    for obj in lead_messages:
        raw_messages.append(("lead", obj))

    subagents_dir = transcript_dir / session_id / "subagents"
    if subagents_dir.exists():
        for sa_jsonl in sorted(subagents_dir.glob("agent-*.jsonl")):
            meta_path = sa_jsonl.with_suffix(".meta.json")
            agent_label = _load_subagent_label(meta_path)
            for obj in _load_jsonl(sa_jsonl):
                raw_messages.append((agent_label, obj))

    # Collect all assistant timestamps for header info
    all_ts = [
        _parse_timestamp(obj.get("timestamp", ""))
        for _, obj in raw_messages
        if obj.get("message", {}).get("role") == "assistant" and obj.get("timestamp")
    ]
    all_ts = [t for t in all_ts if t > 0]

    first_ts = min(all_ts) if all_ts else None
    last_ts = max(all_ts) if all_ts else None

    # Lead time: span of assistant messages in the parent transcript.
    lead_ts = [
        _parse_timestamp(obj.get("timestamp", ""))
        for obj in lead_messages
        if obj.get("message", {}).get("role") == "assistant" and obj.get("timestamp")
    ]
    lead_ts = [t for t in lead_ts if t > 0]
    lead_time_ms = int((max(lead_ts) - min(lead_ts)) * 1000) if len(lead_ts) >= 2 else 0

    print(f"Session: {session_id}")
    if first_ts:
        print(f"Started: {_ts_to_iso(first_ts)}")
    if last_ts:
        print(f"Last activity: {_ts_to_iso(last_ts)}")
    if first_ts and last_ts:
        elapsed = last_ts - first_ts
        print(f"Elapsed: {fmt_time(elapsed)}")
    configured = _load_configured_models()
    if configured:
        entries = ", ".join(f"{role}={model}" for role, model in sorted(configured.items()))
        print(f"Configured: {entries}")
    if since is not None:
        print(f"Filtered: messages from {_ts_to_iso(since)} onward")
    print()

    groups: dict = {}

    for agent_label, obj in raw_messages:
        ts = obj.get("timestamp", "")
        if since is not None and ts and _parse_timestamp(ts) < since:
            continue

        msg = obj.get("message", {})
        if msg.get("role") != "assistant":
            continue

        usage = msg.get("usage")
        if not usage:
            continue

        model = _pricing.normalize_model(msg.get("model", "unknown") or "unknown")
        if model == "<synthetic>":
            continue
        inp = usage.get("input_tokens", 0) or 0
        outp = usage.get("output_tokens", 0) or 0
        cache = usage.get("cache_read_input_tokens", 0) or 0

        key = (agent_label, model)
        if key not in groups:
            groups[key] = {"inp": 0, "outp": 0, "cache": 0}
        groups[key]["inp"] += inp
        groups[key]["outp"] += outp
        groups[key]["cache"] += cache

    if not groups:
        print("No assistant messages found in current session.")
        return 0

    costs = [
        (agent, model, g["inp"], g["outp"], g["cache"],
         _pricing.calculate_cost(model, g["inp"], g["outp"], g["cache"]),
         _pricing.baseline_cost(g["inp"], g["outp"], g["cache"]))
        for (agent, model), g in groups.items()
    ]

    def _time_str_for(label: str) -> str:
        if label == "lead":
            ms = lead_time_ms
        else:
            ms = agent_time_ms.get(label, 0)
        return fmt_time(ms / 1000) if ms > 0 else "n/a"

    total_time_ms = sum(
        lead_time_ms if agent == "lead" else agent_time_ms.get(agent, 0)
        for agent, *_ in costs
    )
    total_time_str = fmt_time(total_time_ms / 1000) if total_time_ms > 0 else "n/a"

    rows = [
        (f"{agent}({model})", model, inp, outp, cache, _time_str_for(agent), actual, vs)
        for agent, model, inp, outp, cache, actual, vs in costs
    ]
    render_cost_table(rows, total_time_str, _pricing.baseline_label())
    return 0
