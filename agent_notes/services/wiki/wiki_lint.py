"""Validation and health checks for the wiki."""

from __future__ import annotations

import re
from pathlib import Path

from ._wiki_utils import (
    WIKI_PAGE_TYPES,
    _collect_all_pages,
    _content_hash,
    _extract_h1,
    _parse_list_field,
)
from .._memory_utils import _parse_frontmatter


def wiki_lint(wiki_root: Path) -> dict[str, list]:
    """Check wiki health.

    Returns {orphans, broken_links, stale_index, needs_compilation,
             contradiction_candidates, stale_pages, data_gaps}.
    """
    issues: dict[str, list] = {
        "orphans": [],
        "broken_links": [],
        "stale_index": [],
        "needs_compilation": [],
        "contradiction_candidates": [],
        "stale_pages": [],
        "data_gaps": [],
    }

    if not wiki_root.exists():
        return issues

    wiki_dir = wiki_root / "wiki"
    all_pages = _collect_all_pages(wiki_dir)
    slugs = {p.stem for p in all_pages}

    page_meta: dict[str, dict] = {}
    linked_slugs: set[str] = set()
    all_referenced_slugs: set[str] = set()

    for page_path in all_pages:
        try:
            text = page_path.read_text()
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        page_meta[page_path.stem] = {"path": page_path, "fm": fm, "body": body}
        links = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", text)
        for link in links:
            link_slug = link.strip()
            linked_slugs.add(link_slug)
            all_referenced_slugs.add(link_slug)
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

    # --- Contradiction candidates: pages sharing tags from different sources ---
    tag_to_pages: dict[str, list[str]] = {}
    for slug, meta in page_meta.items():
        tags = _parse_list_field(meta["fm"].get("tags", ""))
        for tag in tags:
            tag_to_pages.setdefault(tag, []).append(slug)

    seen_pairs: set[tuple[str, str]] = set()
    for tag, page_slugs in tag_to_pages.items():
        if len(page_slugs) < 2:
            continue
        for i, slug_a in enumerate(page_slugs):
            for slug_b in page_slugs[i + 1:]:
                sources_a = _parse_list_field(page_meta[slug_a]["fm"].get("sources", ""))
                sources_b = _parse_list_field(page_meta[slug_b]["fm"].get("sources", ""))
                if sources_a and sources_b and set(sources_a) != set(sources_b):
                    pair = (min(slug_a, slug_b), max(slug_a, slug_b))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        issues["contradiction_candidates"].append(
                            f"[[{pair[0]}]] and [[{pair[1]}]] share tag '{tag}' but have different sources"
                        )

    # --- Stale pages: source pages whose raw content hash has changed ---
    raw_dir = wiki_root / "raw"
    for slug, meta in page_meta.items():
        stored_hash = meta["fm"].get("content_hash", "")
        sources = _parse_list_field(meta["fm"].get("sources", ""))
        raw_sources = [s for s in sources if s.startswith("raw/")]
        if not raw_sources:
            continue
        if not stored_hash:
            issues["stale_pages"].append(f"{meta['path']}: missing content_hash — consider re-ingesting")
            continue
        hash_parts = []
        for raw_ref in raw_sources:
            raw_path = wiki_root / raw_ref
            if raw_path.exists():
                try:
                    hash_parts.append(raw_path.read_text())
                except OSError:
                    continue
        if hash_parts:
            current_hash = _content_hash("".join(hash_parts))
            if current_hash != stored_hash:
                issues["stale_pages"].append(f"{meta['path']}: content_hash mismatch — raw source has changed")

    # --- Data gaps: wikilinks pointing to nonexistent pages ---
    for ref_slug in all_referenced_slugs:
        if ref_slug not in slugs:
            referencing = [s for s, m in page_meta.items() if f"[[{ref_slug}]]" in m.get("body", "")]
            if not referencing:
                referencing = [s for s, m in page_meta.items()
                               if re.search(rf"\[\[{re.escape(ref_slug)}(?:\|[^\]]+)?\]\]",
                                            m["fm"].get("tags", "") + m.get("body", ""))]
            issues["data_gaps"].append(
                f"[[{ref_slug}]]: referenced by {referencing} but no page exists"
            )

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
