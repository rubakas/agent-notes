"""Generate the session context file injected by the SessionStart hook."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def _template_path() -> Path:
    return Path(__file__).parent.parent / "data" / "hooks" / "session-context.md.tpl"


def _render_skills_catalog(skills: list[Any]) -> str:
    if not skills:
        return ""
    sorted_skills = sorted(skills, key=lambda s: s.name)
    lines = ["**Skills** (invoke with /skill-name):"]
    for skill in sorted_skills:
        lines.append(f"- /{skill.name} — {skill.description}")
    return "\n".join(lines)


def render_context(agents: list[str], version: str, skills: list[Any] | None = None) -> str:
    tpl = _template_path().read_text()
    if agents:
        agents_list = "\n".join(f"- {name}" for name in sorted(agents))
    else:
        agents_list = "- (see ~/.claude/agents/ for installed agents)"
    skills_catalog = _render_skills_catalog(skills) if skills else ""
    return (tpl
            .replace("{{version}}", version)
            .replace("{{agents_list}}", agents_list)
            .replace("{{skills_catalog}}", skills_catalog))


def write_context(dest: Path, agents: list[str], version: str, skills: list[Any] | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_context(agents, version, skills))
