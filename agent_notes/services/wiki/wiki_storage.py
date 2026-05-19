"""CRUD operations for wiki page lifecycle."""

from __future__ import annotations

from pathlib import Path

from ._wiki_utils import (
    WIKI_PAGE_TYPES,
    _atomic_write,
    _build_page_content,
    _build_page_frontmatter,
    _ensure_wiki_init,
    _log_operation,
    _merge_unique,
    _parse_list_field,
    _render_empty_index,
    _validate_page_type,
)
from .._memory_utils import _slug, _now_iso, _parse_frontmatter
from ...constants import Wiki


def wiki_init(wiki_root: Path) -> None:
    """Create raw/, wiki/ tree with all subdirs, seed index.md and log.md."""
    (wiki_root / Wiki.RAW_DIR).mkdir(parents=True, exist_ok=True)
    ignore_path = wiki_root / Wiki.IGNORE_FILE
    if not ignore_path.exists():
        _atomic_write(ignore_path, f"{Wiki.RAW_DIR}/\n")
    wiki_dir = wiki_root / Wiki.DIR
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for sub in WIKI_PAGE_TYPES:
        (wiki_dir / sub).mkdir(exist_ok=True)

    index_path = wiki_dir / Wiki.INDEX
    if not index_path.exists():
        _atomic_write(index_path, _render_empty_index())

    log_path = wiki_dir / Wiki.LOG
    if not log_path.exists():
        _atomic_write(log_path, "# Wiki Log\n")


def wiki_write_page(
    wiki_root: Path,
    *,
    title: str,
    body: str,
    page_type: str,
    agent: str = "",
    project: str = "",
    tags: list[str] | None = None,
    aliases: list[str] | None = None,
    sources: list[str] | None = None,
    confidence: str | None = None,
    content_hash: str = "",
) -> Path:
    """Write or update a wiki page.

    If the page already exists, append body under ## Update <timestamp>.
    Triggers cross-referencing and index/log update. Returns the page path.
    """
    from .wiki_index import _cross_reference, wiki_regenerate_index  # avoid circular at module level

    _validate_page_type(page_type)
    _ensure_wiki_init(wiki_root)

    wiki_dir = wiki_root / Wiki.DIR
    folder = wiki_dir / page_type
    folder.mkdir(parents=True, exist_ok=True)

    slug = _slug(title)
    page_path = folder / f"{slug}.md"

    now = _now_iso()

    if page_path.exists():
        text = page_path.read_text()
        fm, existing_body = _parse_frontmatter(text)
        existing_tags = _parse_list_field(fm.get("tags", ""))
        merged_tags = _merge_unique(existing_tags, tags or [])
        existing_aliases = _parse_list_field(fm.get("aliases", ""))
        merged_aliases = _merge_unique(existing_aliases, aliases or [])
        new_fm = _build_page_frontmatter(
            created_at=fm.get("created_at", now),
            updated_at=now,
            page_type=page_type,
            agent=agent or fm.get("agent", ""),
            project=project or fm.get("project", ""),
            tags=merged_tags,
            aliases=merged_aliases,
            sources=sources or _parse_list_field(fm.get("sources", "")),
            confidence=confidence or fm.get("confidence", ""),
            content_hash=content_hash or fm.get("content_hash", ""),
        )
        new_content = new_fm + existing_body.rstrip() + f"\n\n## Update {now}\n\n{body}\n"
        _atomic_write(page_path, new_content)
        action_label = "updated"
    else:
        content = _build_page_content(
            title=title,
            body=body,
            page_type=page_type,
            created_at=now,
            updated_at=now,
            agent=agent,
            project=project,
            tags=tags or [],
            aliases=aliases or [],
            sources=sources or [],
            confidence=confidence or "",
            content_hash=content_hash,
        )
        _atomic_write(page_path, content)
        action_label = "created"

    cross_ref_count = _cross_reference(wiki_dir, [page_path])
    wiki_regenerate_index(wiki_root)
    _log_operation(
        wiki_root,
        operation="add",
        title=title,
        details=f"- {page_type}: {page_path.relative_to(wiki_root)} ({action_label})\n- cross-refs: {cross_ref_count} links inserted",
    )

    return page_path
