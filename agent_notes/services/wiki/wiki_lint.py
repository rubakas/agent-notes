"""Validation and health checks for the wiki."""

from __future__ import annotations

import re
from pathlib import Path

from ._wiki_utils import (
    WIKI_PAGE_TYPES,
    _collect_all_pages,
    _extract_h1,
    _parse_list_field,
)
from .._memory_utils import _parse_frontmatter


def wiki_lint(wiki_root: Path) -> dict[str, list]:
    """Check wiki health.

    Returns {orphans: [...], broken_links: [...], stale_index: [...], needs_compilation: [...]}.
    """
    issues: dict[str, list] = {"orphans": [], "broken_links": [], "stale_index": [], "needs_compilation": []}

    if not wiki_root.exists():
        return issues

    wiki_dir = wiki_root / "wiki"
    all_pages = _collect_all_pages(wiki_dir)
    slugs = {p.stem for p in all_pages}

    linked_slugs: set[str] = set()
    for page_path in all_pages:
        try:
            text = page_path.read_text()
        except OSError:
            continue
        links = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", text)
        for link in links:
            link_slug = link.strip()
            linked_slugs.add(link_slug)
            if link_slug not in slugs:
                issues["broken_links"].append(f"{page_path}: broken link [[{link_slug}]]")

    for page_path in all_pages:
        if page_path.stem not in linked_slugs:
            issues["orphans"].append(str(page_path))

    index_path = wiki_dir / "index.md"
    if index_path.exists():
        index_mtime = index_path.stat().st_mtime
        for page_path in all_pages:
            if page_path.stat().st_mtime > index_mtime:
                issues["stale_index"].append(str(page_path))

    _stub_pattern = re.compile(r"^\s*Referenced from source:\s*\[\[[^\]]+\]\]\s*$", re.MULTILINE)
    for stub_type in ("concepts", "entities"):
        folder = wiki_dir / stub_type
        if not folder.exists():
            continue
        for page_path in sorted(folder.glob("*.md")):
            try:
                text = page_path.read_text()
            except OSError:
                continue
            _, body = _parse_frontmatter(text)
            stripped = re.split(r"\n## (?:Related|Update\b)", body)[0]
            stripped = re.sub(r"^#[^\n]*\n", "", stripped, count=1)
            stripped = stripped.strip()
            if not stripped or _stub_pattern.match(stripped):
                issues["needs_compilation"].append(str(page_path))

    return issues


def wiki_list_pages(wiki_root: Path) -> list[dict]:
    """Return metadata for all wiki pages (for `memory list` command)."""
    if not wiki_root.exists():
        return []

    wiki_dir = wiki_root / "wiki"
    pages = []
    for page_type in WIKI_PAGE_TYPES:
        folder = wiki_dir / page_type
        if not folder.exists():
            continue
        for page_path in sorted(folder.glob("*.md")):
            try:
                text = page_path.read_text()
            except OSError:
                continue
            fm, _ = _parse_frontmatter(text)
            title = _extract_h1(text) or page_path.stem
            pages.append({
                "type": page_type,
                "file": page_path.name,
                "path": str(page_path),
                "title": title,
                "tags": _parse_list_field(fm.get("tags", "")),
                "updated_at": fm.get("updated_at", fm.get("created_at", "")),
            })
    return pages
