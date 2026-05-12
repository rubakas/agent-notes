"""Local file-system memory backend — per-agent subdirectory storage."""

from __future__ import annotations
from pathlib import Path

from ._memory_utils import _today


def local_init(memory_dir: Path) -> None:
    memory_dir.mkdir(parents=True, exist_ok=True)


def local_list_notes(memory_dir: Path) -> list[dict]:
    if not memory_dir.exists():
        return []
    return [
        {"agent": d.name, "path": str(d), "size": sum(f.stat().st_size for f in d.rglob("*") if f.is_file())}
        for d in sorted(memory_dir.iterdir()) if d.is_dir()
    ]


def local_regenerate_index(memory_dir: Path) -> None:
    agents = [d.name for d in sorted(memory_dir.iterdir()) if d.is_dir()] if memory_dir.exists() else []
    lines = [f"# Agent Memory", f"Last updated: {_today()}", ""]
    for agent in agents:
        agent_dir = memory_dir / agent
        files = list(agent_dir.glob("*.md"))
        lines.append(f"## {agent} ({len(files)} files)")
        for f in sorted(files):
            lines.append(f"- [{f.stem}]({agent}/{f.name})")
        lines.append("")
    (memory_dir / "Index.md").write_text("\n".join(lines))
