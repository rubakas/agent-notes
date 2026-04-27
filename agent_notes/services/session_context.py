"""Generate the session context file injected by the SessionStart hook."""
from __future__ import annotations
from pathlib import Path


def _template_path() -> Path:
    return Path(__file__).parent.parent / "data" / "hooks" / "session-context.md.tpl"


def render_context(agents: list[str], version: str) -> str:
    tpl = _template_path().read_text()
    if agents:
        agents_list = "\n".join(f"- {name}" for name in sorted(agents))
    else:
        agents_list = "- (see ~/.claude/agents/ for installed agents)"
    return (tpl
            .replace("{{version}}", version)
            .replace("{{agents_list}}", agents_list))


def write_context(dest: Path, agents: list[str], version: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_context(agents, version))
