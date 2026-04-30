"""Memory backend implementations for the three storage strategies.

Single rule for ALL records (see skills/obsidian-memory/SKILL.md):
  - Filenames: `YYYY-MM-DD_<slug>.md`; collision → append `_HHMMSS` before `.md`.
  - Session notes use `YYYY-MM-DD_<session-id>.md` (date from created_at or mtime).
  - Frontmatter: `created_at: <ISO 8601 UTC with Z>` — no local time anywhere.
  - Auto-linking: writing a non-session note while a session is active appends a
    wikilink to that session's `## Linked notes` section automatically.
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


def _now_hhmmss() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S")


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


def _current_project_name() -> str:
    """Return the current working directory's name as the project name."""
    name = Path.cwd().name
    return name or ""


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


def _build_filename(date_str: str, slug_part: str, folder: Path) -> str:
    """Build `YYYY-MM-DD_<slug>.md`, appending `_HHMMSS` on collision."""
    candidate = f"{date_str}_{slug_part}.md"
    if not (folder / candidate).exists():
        return candidate
    ts = _now_hhmmss()
    return f"{date_str}_{slug_part}_{ts}.md"


def _build_note(
    *,
    title: str,
    body: str,
    note_type: str,
    agent: str,
    session_stem: Optional[str],
    created_at: str,
    project: str = "",
) -> str:
    """Render the canonical note content (frontmatter + heading + body + Related section)."""
    lines = ["---", f"created_at: {created_at}", f"type: {note_type}"]
    if project:
        lines.append(f"project: {project}")
    if session_stem and note_type != "session":
        lines.append(f"session: {session_stem}")
    if agent:
        lines.append(f"agent: {agent}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(body)
    lines.append("")
    lines.append("## Related")
    lines.append("")
    return "\n".join(lines)


def _find_session_note(vault: Path, session_id: str) -> Optional[Path]:
    """Find the session note file for the given session_id (matches stem pattern YYYY-MM-DD_<id>)."""
    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        return None
    for f in sessions_dir.glob("*.md"):
        # New format: YYYY-MM-DD_<session-id>.md  → stem ends with _<session-id>
        if f.stem.endswith(f"_{session_id}") or f.stem == session_id:
            return f
    return None


def _append_linked_note(session_path: Path, stem: str, note_type: str, title: str) -> None:
    """Append a wikilink line to the session note's ## Linked notes section (idempotent)."""
    content = session_path.read_text()
    link_line = f"- [[{stem}]] — {note_type} — {title}"
    if link_line in content:
        return

    if "## Linked notes" in content:
        content = content.rstrip() + f"\n{link_line}\n"
    else:
        content = content.rstrip() + f"\n\n## Linked notes\n\n{link_line}\n"
    session_path.write_text(content)


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

    raw_session_id = _current_session_id()
    if raw_session_id is not None:
        session_id: str | None = _safe_session_id(raw_session_id) or None
    else:
        session_id = None

    if not project:
        project = _current_project_name()

    today = _today()

    if note_type == "session" and session_id:
        filename = _build_filename(today, session_id, folder)
        # But first check if an existing file already has this session_id (any date prefix)
        existing = _find_session_note(vault, session_id)
        if existing is not None:
            # Append to existing session note — preserve existing frontmatter (including project)
            text = existing.read_text()
            fm, existing_body = _parse_frontmatter(text)
            if "created_at" not in fm:
                created_at = fm.get("date", _now_iso())
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", created_at):
                    created_at = f"{created_at}T00:00:00Z"
                new_fm_lines = ["---", f"created_at: {created_at}", f"type: {note_type}"]
                existing_project = fm.get("project", "")
                if existing_project:
                    new_fm_lines.append(f"project: {existing_project}")
                if agent:
                    new_fm_lines.append(f"agent: {agent}")
                new_fm_lines.append("---")
                existing.write_text("\n".join(new_fm_lines) + f"\n\n{existing_body.rstrip()}\n")
            with open(existing, "a") as fh:
                fh.write(f"\n\n## Update {_now_iso()}\n\n{body}\n")
            obsidian_regenerate_index(vault)
            return existing
        # New session note
        created_at = _now_iso()
        path = folder / filename
        path.write_text(_build_note(
            title=title, body=body, note_type=note_type,
            agent=agent, session_stem=None, created_at=created_at, project=project,
        ))
    elif note_type == "session":
        # No session_id available — fall back to timestamp+slug
        filename = _build_filename(today, _slug(title), folder)
        created_at = _now_iso()
        path = folder / filename
        path.write_text(_build_note(
            title=title, body=body, note_type=note_type,
            agent=agent, session_stem=None, created_at=created_at, project=project,
        ))
    else:
        # Non-session note
        session_stem: Optional[str] = None
        if session_id:
            existing_session = _find_session_note(vault, session_id)
            if existing_session:
                session_stem = existing_session.stem
            else:
                session_stem = f"{today}_{session_id}"

        filename = _build_filename(today, _slug(title), folder)
        created_at = _now_iso()
        path = folder / filename
        path.write_text(_build_note(
            title=title, body=body, note_type=note_type,
            agent=agent, session_stem=session_stem, created_at=created_at, project=project,
        ))

        # Auto-link to session note
        if session_id:
            session_note = _find_session_note(vault, session_id)
            if session_note is not None:
                _append_linked_note(session_note, path.stem, note_type, title)

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
    project = fm.get("project", "")
    return {"created_at": created_at, "type": note_type, "title": title, "project": project}


def obsidian_regenerate_index(vault: Path) -> None:
    """Regenerate Index.md as a chronological list of all notes, newest first."""
    now_iso = _now_iso()

    all_notes: list[tuple[str, Path]] = []
    for cat in OBSIDIAN_CATEGORIES:
        folder = vault / cat
        if not folder.exists():
            continue
        for note in folder.glob("*.md"):
            all_notes.append((cat, note))

    note_metas: list[dict] = []
    for cat, note in all_notes:
        meta = _parse_note_metadata(note)
        meta["_path"] = note
        meta["_category"] = cat
        note_metas.append(meta)

    note_metas.sort(key=lambda m: m["created_at"], reverse=True)

    lines = [f"# Agent Memory Index", "", f"Last updated: {now_iso}", ""]
    for meta in note_metas:
        note: Path = meta["_path"]
        stem = note.stem
        dt_str = meta["created_at"]
        # Format: YYYY-MM-DD HH:MM from the ISO timestamp
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", dt_str):
            display_dt = f"{dt_str[:10]} {dt_str[11:16]}"
        else:
            display_dt = dt_str[:16] if len(dt_str) >= 16 else dt_str
        project = meta.get("project", "")
        lines.append(f"- [[{stem}|{display_dt}]] - {project}({meta['type']})")

    (vault / "Index.md").write_text("\n".join(lines) + "\n")


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
