"""Memory backend implementations for the three storage strategies."""

from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


OBSIDIAN_CATEGORIES = ["Patterns", "Decisions", "Mistakes", "Context", "Sessions"]


def _slug(title: str) -> str:
    title = re.sub(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}[:\-]\d{2}[:\-]\d{2}\s*", "", title)
    title = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", title)
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ── Obsidian backend ───────────────────────────────────────────────────────────

def obsidian_init(vault: Path) -> None:
    """Create category folders and a stub Index.md if the vault is new."""
    vault.mkdir(parents=True, exist_ok=True)
    for cat in OBSIDIAN_CATEGORIES:
        (vault / cat).mkdir(exist_ok=True)
    index = vault / "Index.md"
    if not index.exists():
        obsidian_regenerate_index(vault)


def obsidian_write_note(
    vault: Path,
    *,
    title: str,
    body: str,
    note_type: str,  # "pattern"|"decision"|"mistake"|"context"|"session"
    agent: str = "",
    project: str = "",
    tags: list[str] | None = None,
) -> Path:
    """Write a structured note to the correct category folder."""
    category_map = {
        "pattern": "Patterns",
        "decision": "Decisions",
        "mistake": "Mistakes",
        "context": "Context",
        "session": "Sessions",
    }
    folder = vault / category_map.get(note_type, "Context")
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{_now()}-{_slug(title)}.md"
    path = folder / filename

    frontmatter_lines = [
        "---",
        f"date: {_today()}",
        f"type: {note_type}",
    ]
    if agent:
        frontmatter_lines.append(f"agent: {agent}")
    if project:
        frontmatter_lines.append(f"project: {project}")
    if tags:
        frontmatter_lines.append(f"tags: [{', '.join(tags)}]")
    frontmatter_lines.append("---")

    path.write_text("\n".join(frontmatter_lines) + f"\n\n# {title}\n\n{body}\n")
    obsidian_regenerate_index(vault)
    return path


def obsidian_regenerate_index(vault: Path) -> None:
    """Regenerate Index.md from all notes in the vault (last 20 per category)."""
    lines = [f"# Agent Memory Index", f"Last updated: {_today()}", ""]
    for cat in OBSIDIAN_CATEGORIES:
        folder = vault / cat
        if not folder.exists():
            continue
        notes = sorted(folder.glob("*.md"), reverse=True)[:20]
        if not notes:
            continue
        lines.append(f"## {cat} ({len(list(folder.glob('*.md')))})")
        for note in notes:
            stem = note.stem
            # Extract title from first H1 if possible
            try:
                first_h1 = next(
                    (l.lstrip("# ").strip() for l in note.read_text().splitlines() if l.startswith("# ")),
                    stem,
                )
            except OSError:
                first_h1 = stem
            lines.append(f"- [[{stem}]] — {first_h1}")
        lines.append("")
    (vault / "Index.md").write_text("\n".join(lines))


def obsidian_list_notes(vault: Path) -> list[dict]:
    """Return list of note metadata dicts from the vault."""
    notes = []
    for cat in OBSIDIAN_CATEGORIES:
        folder = vault / cat
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*.md")):
            notes.append({"category": cat, "file": f.name, "path": str(f)})
    return notes


def obsidian_claude_md_section(vault: Path) -> str:
    return (
        f"## Agent Memory\n\n"
        f"Your memory vault is at `{vault}`. Start at `Index.md` to find relevant context.\n"
        f"Categories: Patterns, Decisions, Mistakes, Context, Sessions.\n"
        f"Use `agent-notes memory add` to save insights, `agent-notes memory index` to refresh Index.md."
    )


# ── Local backend ──────────────────────────────────────────────────────────────

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


def local_claude_md_section(memory_dir: Path) -> str:
    return (
        f"## Agent Memory\n\n"
        f"Your memory is at `{memory_dir}/`. Each agent has its own subdirectory.\n"
        f"Files are plain markdown — read and write freely."
    )
