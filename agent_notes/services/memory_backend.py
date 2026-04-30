"""Memory backend implementations for the three storage strategies.

Single rule for ALL records (see skills/obsidian-memory/SKILL.md):
  - Filenames: `<UTC-YYYY-MM-DD-HH-MM-SS>-<slug>.md`, except session notes use `<session-id>.md`.
  - Frontmatter: `created_at: <ISO 8601 UTC with Z>` — no local time anywhere.
"""

from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


OBSIDIAN_CATEGORIES = ["Patterns", "Decisions", "Mistakes", "Context", "Sessions"]


def _slug(title: str) -> str:
    title = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\s*", "", title)
    title = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", title)
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _current_session_id() -> Optional[str]:
    """Detect the current CLI's session ID. Returns None if not in a known CLI session."""
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        slug = str(Path.cwd()).replace("/", "-")
        proj = Path.home() / ".claude" / "projects" / slug
        if proj.is_dir():
            jsonls = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if jsonls:
                return jsonls[0].stem
    return None


# ── Obsidian backend ───────────────────────────────────────────────────────────

def obsidian_init(vault: Path) -> None:
    """Create category folders and a stub Index.md if the vault is new."""
    vault.mkdir(parents=True, exist_ok=True)
    for cat in OBSIDIAN_CATEGORIES:
        (vault / cat).mkdir(exist_ok=True)
    index = vault / "Index.md"
    if not index.exists():
        obsidian_regenerate_index(vault)


def _safe_session_id(sid: str) -> str:
    sid = re.sub(r"[^A-Za-z0-9_-]", "", sid)
    return sid[:128]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a file into (frontmatter_dict, body_after_frontmatter).

    Returns an empty dict if the file does not start with '---'.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    rest = text[end + 4:].lstrip("\n")
    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, rest


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

    raw_session_id = _current_session_id() if note_type == "session" else None
    if raw_session_id is not None:
        session_id: str | None = _safe_session_id(raw_session_id) or None
    else:
        session_id = None

    if note_type == "session" and session_id:
        filename = f"{session_id}.md"
    else:
        filename = f"{_now()}-{_slug(title)}.md"
    path = folder / filename

    def _build_frontmatter(created_at: str) -> str:
        lines = [
            "---",
            f"created_at: {created_at}",
            f"type: {note_type}",
        ]
        if session_id:
            lines.append(f"session_id: {session_id}")
        if agent:
            lines.append(f"agent: {agent}")
        if project:
            lines.append(f"project: {project}")
        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")
        lines.append("---")
        return "\n".join(lines)

    if path.exists() and note_type == "session":
        existing = path.read_text()
        fm, existing_body = _parse_frontmatter(existing)

        if "created_at" not in fm:
            # Stale frontmatter — rewrite it, preserving original date if available
            created_at = fm.get("date", _now_iso())
            # Normalise bare date (YYYY-MM-DD) to ISO UTC
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", created_at):
                created_at = f"{created_at}T00:00:00Z"
            new_frontmatter = _build_frontmatter(created_at)
            path.write_text(new_frontmatter + f"\n\n{existing_body.rstrip()}\n")

        with open(path, "a") as fh:
            fh.write(f"\n\n## Update {_now_iso()}\n\n{body}\n")
    else:
        path.write_text(_build_frontmatter(_now_iso()) + f"\n\n# {title}\n\n{body}\n")
    obsidian_regenerate_index(vault)
    return path


def _parse_note_metadata(path: Path) -> dict:
    """Return {"created_at": "...", "type": "...", "title": "<H1>"} for a note file."""
    try:
        text = path.read_text()
    except OSError:
        return {"created_at": "", "type": "", "title": path.stem}
    fm, body = _parse_frontmatter(text)
    note_type = fm.get("type", "")
    created_at = fm.get("created_at", "")
    if not created_at:
        legacy = fm.get("date", "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", legacy):
            created_at = f"{legacy}T00:00:00Z"
        else:
            created_at = legacy
    full_text = text
    title = next(
        (l.lstrip("# ").strip() for l in full_text.splitlines() if l.startswith("# ")),
        path.stem,
    )
    return {"created_at": created_at, "type": note_type, "title": title}


def obsidian_regenerate_index(vault: Path) -> None:
    """Regenerate Index.md with a chronological 'Recent activity' section + per-category breakdown."""
    now_iso = _now_iso()

    # Collect all notes across all categories
    all_notes: list[tuple[str, Path]] = []  # (category, path)
    for cat in OBSIDIAN_CATEGORIES:
        folder = vault / cat
        if not folder.exists():
            continue
        for note in folder.glob("*.md"):
            all_notes.append((cat, note))

    # Build recent activity list (sorted by created_at descending)
    note_metas: list[dict] = []
    for cat, note in all_notes:
        meta = _parse_note_metadata(note)
        meta["_path"] = note
        meta["_category"] = cat
        note_metas.append(meta)

    note_metas.sort(key=lambda m: m["created_at"], reverse=True)
    recent = note_metas[:30]

    lines = ["# Agent Memory Index", "", f"Last updated: {now_iso}", "", "## Recent activity", ""]
    for meta in recent:
        note: Path = meta["_path"]
        stem = note.stem
        is_session = meta["_category"] == "Sessions" or meta["type"] == "session"
        if is_session and not re.match(r"^\d{4}-\d{2}-\d{2}-", stem):
            link = f"[[{stem}|{meta['title']}]]"
        else:
            link = f"[[{stem}]]"
        lines.append(f"- [{meta['created_at']}] {link} - {meta['type']}")
    lines.append("")

    # Per-category breakdown
    lines.append("## By category")
    lines.append("")
    for cat in OBSIDIAN_CATEGORIES:
        folder = vault / cat
        if not folder.exists():
            continue
        notes_in_cat = [p for c, p in all_notes if c == cat]
        if not notes_in_cat:
            continue
        notes = sorted(notes_in_cat, reverse=True)[:20]
        lines.append(f"### {cat} ({len(notes_in_cat)})")
        for note in notes:
            stem = note.stem
            try:
                first_h1 = next(
                    (l.lstrip("# ").strip() for l in note.read_text().splitlines() if l.startswith("# ")),
                    stem,
                )
            except OSError:
                first_h1 = stem
            is_session = cat == "Sessions" and not re.match(r"^\d{4}-\d{2}-\d{2}-", stem)
            if is_session:
                lines.append(f"- [[{stem}|{first_h1}]] — {first_h1}")
            else:
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
