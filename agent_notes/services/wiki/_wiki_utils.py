"""Shared helpers: constants, parsing, building, file ops."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from .._memory_utils import _now_iso


WIKI_PAGE_TYPES = ["sources", "concepts", "entities", "synthesis", "sessions"]

_RAW_CHUNK_MAX = 2 * 1024 * 1024  # 2 MB


def _log_operation(wiki_root: Path, operation: str, title: str, details: str = "") -> None:
    """Append structured entry to wiki/log.md."""
    log_path = wiki_root / "wiki" / "log.md"
    if not log_path.exists():
        log_path.write_text("# Wiki Log\n")

    entry = f"\n## [{_now_iso()}] {operation} | {title}\n"
    if details:
        entry += f"\n{details}\n"

    with open(log_path, "a") as fh:
        fh.write(entry)


def _validate_page_type(page_type: str) -> None:
    if page_type not in WIKI_PAGE_TYPES:
        raise ValueError(f"Invalid page_type {page_type!r}. Must be one of: {WIKI_PAGE_TYPES}")


def _ensure_wiki_init(wiki_root: Path) -> None:
    """Auto-initialize wiki_root if it doesn't exist."""
    if not (wiki_root / "wiki").exists():
        from .wiki_storage import wiki_init  # late import to avoid circular dependency
        wiki_init(wiki_root)


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically (temp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp_path, path)
    except Exception:
        os.close(fd)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _build_page_frontmatter(
    *,
    created_at: str,
    updated_at: str,
    page_type: str,
    agent: str = "",
    project: str = "",
    tags: list[str],
    aliases: list[str],
    sources: list[str],
    confidence: str = "",
) -> str:
    lines = ["---", f"created_at: {created_at}", f"updated_at: {updated_at}", f"type: {page_type}"]
    if tags:
        quoted = ", ".join(f'"{v}"' for v in tags)
        lines.append(f"tags: [{quoted}]")
    if aliases:
        quoted = ", ".join(f'"{v}"' for v in aliases)
        lines.append(f"aliases: [{quoted}]")
    if sources:
        quoted = ", ".join(f'"{v}"' for v in sources)
        lines.append(f"sources: [{quoted}]")
    if agent:
        lines.append(f"agent: {agent}")
    if project:
        lines.append(f"project: {project}")
    if confidence:
        lines.append(f'confidence: "{confidence}"')
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _build_page_content(
    *,
    title: str,
    body: str,
    page_type: str,
    created_at: str,
    updated_at: str,
    agent: str,
    project: str,
    tags: list[str],
    aliases: list[str],
    sources: list[str],
    confidence: str = "",
) -> str:
    fm = _build_page_frontmatter(
        created_at=created_at,
        updated_at=updated_at,
        page_type=page_type,
        agent=agent,
        project=project,
        tags=tags,
        aliases=aliases,
        sources=sources,
        confidence=confidence,
    )
    return fm + f"# {title}\n\n{body}\n\n## Related\n\n"


def _render_empty_index() -> str:
    return f"# Wiki Index\n\nLast updated: {_now_iso()}\n"


def _parse_list_field(value: str) -> list[str]:
    """Parse a YAML inline list like '["a", "b"]', '[a, b, c]', or 'a, b, c' into a list."""
    if not value:
        return []
    value = value.strip().strip("[]")
    return [item.strip().strip('"') for item in value.split(",") if item.strip()]


def _merge_unique(existing: list[str], new: list[str]) -> list[str]:
    seen = set(existing)
    result = list(existing)
    for item in new:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _extract_h1(text: str) -> Optional[str]:
    """Return first H1 heading content, or None."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _extract_snippet(body: str, keyword: str, context: int = 80) -> str:
    """Return a short snippet around the first keyword occurrence."""
    body_lower = body.lower()
    idx = body_lower.find(keyword)
    if idx == -1:
        return body[:context].replace("\n", " ").strip()
    start = max(0, idx - context // 2)
    end = min(len(body), idx + len(keyword) + context // 2)
    snippet = body[start:end].replace("\n", " ").strip()
    return snippet


def _one_liner(body: str) -> str:
    """Return the first non-empty, non-heading line from body."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:100]
    return ""


def _collect_all_pages(wiki_dir: Path) -> list[Path]:
    """Return all .md pages in wiki subdirectories."""
    pages = []
    for page_type in WIKI_PAGE_TYPES:
        folder = wiki_dir / page_type
        if folder.exists():
            pages.extend(sorted(folder.glob("*.md")))
    return pages
