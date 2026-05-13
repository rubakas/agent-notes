"""Search and discovery over wiki pages."""

from __future__ import annotations

from pathlib import Path

from ._wiki_utils import (
    WIKI_PAGE_TYPES,
    _extract_h1,
    _extract_snippet,
    _parse_list_field,
)
from .._memory_utils import _parse_frontmatter

import re


def wiki_query(wiki_root: Path, keyword: str) -> list[dict]:
    """Search wiki pages by keyword. Match against titles, aliases, tags, body.

    Returns list of {path, title, type, snippet}.
    """
    if not wiki_root.exists():
        return []

    wiki_dir = wiki_root / "wiki"
    results = []
    kw_lower = keyword.lower()

    for page_type in WIKI_PAGE_TYPES:
        folder = wiki_dir / page_type
        if not folder.exists():
            continue
        for page_path in sorted(folder.glob("*.md")):
            try:
                text = page_path.read_text()
            except OSError:
                continue
            fm, body = _parse_frontmatter(text)

            page_title = _extract_h1(text) or page_path.stem
            aliases = _parse_list_field(fm.get("aliases", ""))
            tags = _parse_list_field(fm.get("tags", ""))

            searchable = " ".join([page_title] + aliases + tags + [body]).lower()
            if kw_lower not in searchable:
                continue

            snippet = _extract_snippet(body, kw_lower)
            results.append({
                "path": str(page_path),
                "title": page_title,
                "type": page_type,
                "snippet": snippet,
            })

    return results


def wiki_scan_raw(wiki_root: Path) -> list[dict]:
    """Scan raw/ for files not yet referenced by any source page.

    Returns list of dicts: {group: str, files: [str], total_size: int}.
    Groups chunks by prefix (e.g. portal-domcap-001.md .. -017.md → group "portal-domcap").
    """
    raw_dir = wiki_root / "raw"
    if not raw_dir.exists():
        return []

    sources_dir = wiki_root / "wiki" / "sources"
    known_refs: set[str] = set()
    if sources_dir.exists():
        for page in sources_dir.glob("*.md"):
            try:
                text = page.read_text()
            except OSError:
                continue
            fm, _ = _parse_frontmatter(text)
            for ref in _parse_list_field(fm.get("sources", "")):
                known_refs.add(ref)

    unprocessed: dict[str, list[Path]] = {}
    chunk_re = re.compile(r"^(.+?)(?:-folder)?-(\d{3})\.md$")

    for f in sorted(raw_dir.iterdir()):
        if not f.is_file():
            continue
        ref = f"raw/{f.name}"
        if ref in known_refs:
            continue

        m = chunk_re.match(f.name)
        group = m.group(1) if m else f.stem
        unprocessed.setdefault(group, []).append(f)

    return [
        {
            "group": group,
            "files": [f.name for f in files],
            "total_size": sum(f.stat().st_size for f in files),
        }
        for group, files in unprocessed.items()
    ]
