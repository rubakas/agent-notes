"""Indexing and cross-referencing for wiki pages."""

from __future__ import annotations

import re
from pathlib import Path

from ._wiki_utils import (
    WIKI_PAGE_TYPES,
    _atomic_write,
    _collect_all_pages,
    _extract_h1,
    _now_iso,
    _one_liner,
    _parse_list_field,
)
from .._memory_utils import _parse_frontmatter


def wiki_regenerate_index(wiki_root: Path) -> None:
    """Rebuild wiki/index.md as markdown tables grouped by category."""
    wiki_dir = wiki_root / "wiki"
    now = _now_iso()

    sections = []
    for page_type in WIKI_PAGE_TYPES:
        folder = wiki_dir / page_type
        if not folder.exists():
            continue
        pages = []
        for page_path in sorted(folder.glob("*.md")):
            try:
                text = page_path.read_text()
            except OSError:
                continue
            fm, body = _parse_frontmatter(text)
            title = _extract_h1(text) or page_path.stem
            tags_list = _parse_list_field(fm.get("tags", ""))
            tags_str = " ".join(f"#{t}" for t in tags_list) if tags_list else ""
            updated = (fm.get("updated_at", fm.get("created_at", "")))[:10]
            summary = _one_liner(body)
            pages.append((page_path.stem, summary, tags_str, updated))

        if not pages:
            continue

        label = page_type.capitalize()
        lines = [f"## {label} ({len(pages)})", "", "| Page | Tags | Updated |", "|------|------|---------|"]
        for slug, summary, tags_str, updated in pages:
            summary_cell = f"[[{slug}]]"
            if summary:
                summary_cell += f" — {summary}"
            lines.append(f"| {summary_cell} | {tags_str} | {updated} |")
        sections.append("\n".join(lines))

    content = f"# Wiki Index\n\nLast updated: {now}\n\n" + "\n\n".join(sections) + "\n"
    _atomic_write(wiki_dir / "index.md", content)


def _cross_reference(wiki_dir: Path, touched_pages: list[Path]) -> int:
    """Insert bidirectional wikilinks between related pages.

    Returns count of links inserted.
    """
    registry = _build_title_registry(wiki_dir)
    all_pages = _collect_all_pages(wiki_dir)

    links_inserted = 0

    for touched in touched_pages:
        try:
            touched_text = touched.read_text()
        except OSError:
            continue
        _, touched_body = _parse_frontmatter(touched_text)
        touched_slug = touched.stem

        for other in all_pages:
            if other == touched:
                continue
            other_slug = other.stem

            try:
                other_text = other.read_text()
            except OSError:
                continue
            _, other_body = _parse_frontmatter(other_text)

            touched_names = _names_for_slug(touched_slug, registry)
            if _body_mentions_any(other_body, touched_names, exclude_wikilinks=True):
                added = _ensure_related_section(other, [touched])
                links_inserted += added

            other_names = _names_for_slug(other_slug, registry)
            if _body_mentions_any(touched_body, other_names, exclude_wikilinks=True):
                added = _ensure_related_section(touched, [other])
                links_inserted += added

    return links_inserted


def _names_for_slug(slug: str, registry: dict[str, Path]) -> list[str]:
    """Return all name keys in registry that map to the given slug's path."""
    target = None
    for name, path in registry.items():
        if path.stem == slug:
            target = path
            break
    if target is None:
        return [slug.replace("-", " ")]
    return [name for name, p in registry.items() if p == target]


def _body_mentions_any(body: str, names: list[str], exclude_wikilinks: bool = True) -> bool:
    """Return True if body mentions any of the given names (case-insensitive)."""
    search_body = body
    if exclude_wikilinks:
        search_body = re.sub(r"\[\[[^\]]*\]\]", "", body)
    body_lower = search_body.lower()
    for name in names:
        if name.lower() in body_lower:
            return True
    return False


def _build_title_registry(wiki_dir: Path) -> dict[str, Path]:
    """Map normalized titles and aliases to page paths."""
    registry: dict[str, Path] = {}
    for page_path in _collect_all_pages(wiki_dir):
        try:
            text = page_path.read_text()
        except OSError:
            continue
        fm, _ = _parse_frontmatter(text)
        registry[page_path.stem.replace("-", " ")] = page_path
        registry[page_path.stem] = page_path
        h1 = _extract_h1(text)
        if h1:
            registry[h1.lower()] = page_path
        for alias in _parse_list_field(fm.get("aliases", "")):
            if alias:
                registry[alias.lower()] = page_path
    return registry


def _ensure_related_section(page_path: Path, linked_pages: list[Path]) -> int:
    """Add missing entries to a page's ## Related section. Idempotent.

    Returns number of new links added.
    """
    try:
        content = page_path.read_text()
    except OSError:
        return 0

    added = 0
    for linked in linked_pages:
        if linked == page_path:
            continue
        link_entry = f"- [[{linked.stem}]]"
        if any(line.strip() == link_entry for line in content.splitlines()):
            continue
        if "## Related" in content:
            content = content.rstrip() + f"\n{link_entry}\n"
        else:
            content = content.rstrip() + f"\n\n## Related\n\n{link_entry}\n"
        added += 1

    if added:
        _atomic_write(page_path, content)
    return added
