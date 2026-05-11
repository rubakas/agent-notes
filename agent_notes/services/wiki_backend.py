"""Wiki memory backend — Karpathy-style LLM Wiki with auto cross-referencing.

Directory layout managed by this module:
  <wiki_root>/
    raw/                 # Immutable source material
    wiki/
      index.md           # Content catalog (auto-generated)
      log.md             # Append-only operation log
      sources/           # Summaries of raw material
      concepts/          # Topic pages
      entities/          # People, tools, projects
      synthesis/         # Cross-cutting overviews
      sessions/          # Session tracking
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Optional


WIKI_PAGE_TYPES = ["sources", "concepts", "entities", "synthesis", "sessions"]

_RAW_CHUNK_MAX = 2 * 1024 * 1024  # 2 MB

# Re-use helpers from memory_backend rather than duplicating them
from .memory_backend import (
    _slug,
    _now_iso,
    _today,
    _parse_frontmatter,
)


# ── Init ──────────────────────────────────────────────────────────────────────

def wiki_init(wiki_root: Path) -> None:
    """Create raw/, wiki/ tree with all subdirs, seed index.md and log.md."""
    (wiki_root / "raw").mkdir(parents=True, exist_ok=True)
    ignore_path = wiki_root / ".obsidianignore"
    if not ignore_path.exists():
        _atomic_write(ignore_path, "raw/\n")
    wiki_dir = wiki_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for sub in WIKI_PAGE_TYPES:
        (wiki_dir / sub).mkdir(exist_ok=True)

    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        _atomic_write(index_path, _render_empty_index())

    log_path = wiki_dir / "log.md"
    if not log_path.exists():
        _atomic_write(log_path, "# Wiki Log\n")


# ── Write page ────────────────────────────────────────────────────────────────

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
) -> Path:
    """Write or update a wiki page.

    If the page already exists, append body under ## Update <timestamp>.
    Triggers cross-referencing and index/log update. Returns the page path.
    """
    _validate_page_type(page_type)
    _ensure_wiki_init(wiki_root)

    wiki_dir = wiki_root / "wiki"
    folder = wiki_dir / page_type
    folder.mkdir(parents=True, exist_ok=True)

    slug = _slug(title)
    page_path = folder / f"{slug}.md"

    now = _now_iso()

    if page_path.exists():
        text = page_path.read_text()
        fm, existing_body = _parse_frontmatter(text)
        # Merge tags
        existing_tags = _parse_list_field(fm.get("tags", ""))
        merged_tags = _merge_unique(existing_tags, tags or [])
        # Merge aliases
        existing_aliases = _parse_list_field(fm.get("aliases", ""))
        merged_aliases = _merge_unique(existing_aliases, aliases or [])
        # Build updated frontmatter
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
        )
        _atomic_write(page_path, content)
        action_label = "created"

    # Cross-reference and update catalog
    cross_ref_count = _cross_reference(wiki_dir, [page_path])
    wiki_regenerate_index(wiki_root)
    _log_operation(
        wiki_root,
        operation="add",
        title=title,
        details=f"- {page_type}: {page_path.relative_to(wiki_root)} ({action_label})\n- cross-refs: {cross_ref_count} links inserted",
    )

    return page_path


# ── Ingest ────────────────────────────────────────────────────────────────────

def wiki_ingest(
    wiki_root: Path,
    *,
    title: str,
    body: str,
    raw_content: str = "",
    raw_filename: str = "",
    raw_files: list[tuple[str, str]] | None = None,
    concepts: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
    confidence: str | None = None,
) -> dict[str, list[Path]]:
    """Ingest a source: store raw, create source page, fan out to concepts/entities.

    Returns {"source": [path], "concepts": [paths], "entities": [paths]}.
    """
    _ensure_wiki_init(wiki_root)

    result: dict[str, list[Path]] = {"source": [], "concepts": [], "entities": []}

    # Store raw content
    raw_refs: list[str] = []
    if raw_files:
        for fname, fcontent in raw_files:
            raw_path = wiki_root / "raw" / fname
            _atomic_write(raw_path, fcontent)
            raw_refs.append(f"raw/{fname}")
    elif raw_content:
        if not raw_filename:
            raw_filename = f"{_slug(title)}.md"
        raw_path = wiki_root / "raw" / raw_filename
        _atomic_write(raw_path, raw_content)
        raw_refs.append(f"raw/{raw_filename}")

    # Create/update source page
    source_path = wiki_write_page(
        wiki_root,
        title=title,
        body=body,
        page_type="sources",
        tags=tags or [],
        sources=raw_refs if raw_refs else [],
        confidence=confidence,
    )
    result["source"].append(source_path)

    # Fan out to concept pages
    for concept_title in (concepts or []):
        cp = wiki_write_page(
            wiki_root,
            title=concept_title,
            body=f"Referenced from source: [[{_slug(title)}]]",
            page_type="concepts",
            tags=tags or [],
            confidence=confidence,
        )
        result["concepts"].append(cp)

    # Fan out to entity pages
    for entity_title in (entities or []):
        ep = wiki_write_page(
            wiki_root,
            title=entity_title,
            body=f"Referenced from source: [[{_slug(title)}]]",
            page_type="entities",
            tags=tags or [],
            confidence=confidence,
        )
        result["entities"].append(ep)

    touched: list[Path] = result["source"] + result["concepts"] + result["entities"]
    wiki_dir = wiki_root / "wiki"
    cross_ref_count = _cross_reference(wiki_dir, touched)
    wiki_regenerate_index(wiki_root)

    details_lines = [f"- source: {source_path.relative_to(wiki_root)} (created/updated)"]
    for cp in result["concepts"]:
        details_lines.append(f"- concept: {cp.relative_to(wiki_root)} (created/updated)")
    for ep in result["entities"]:
        details_lines.append(f"- entity: {ep.relative_to(wiki_root)} (created/updated)")
    details_lines.append(f"- cross-refs: {cross_ref_count} links inserted")

    _log_operation(wiki_root, operation="ingest", title=title, details="\n".join(details_lines))

    return result


# ── Ingest from file ──────────────────────────────────────────────────────────

def wiki_ingest_file(
    wiki_root: Path,
    *,
    file_path: Path,
    title: str = "",
    body: str = "",
    concepts: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, list[Path]]:
    """Ingest a local file into the wiki. Reads content, derives title, delegates to wiki_ingest."""
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    raw_content = file_path.read_text(errors="replace")
    if not title:
        title = file_path.stem.replace("-", " ").replace("_", " ").title()
    if not body:
        body = f"Ingested from local file: {file_path}"

    if len(raw_content.encode()) > _RAW_CHUNK_MAX:
        slug = _slug(title)
        lines = raw_content.split("\n")
        chunks: list[tuple[str, str]] = []
        current_lines: list[str] = []
        current_size = 0

        for line in lines:
            line_size = len(line.encode()) + 1
            if current_lines and current_size + line_size > _RAW_CHUNK_MAX:
                chunk_num = len(chunks) + 1
                fname = f"{slug}-{chunk_num:03d}.md"
                chunks.append((fname, "\n".join(current_lines)))
                current_lines = [line]
                current_size = line_size
            else:
                current_lines.append(line)
                current_size += line_size

        if current_lines:
            chunk_num = len(chunks) + 1
            fname = f"{slug}-{chunk_num:03d}.md"
            chunks.append((fname, "\n".join(current_lines)))

        return wiki_ingest(
            wiki_root,
            title=title,
            body=body,
            raw_files=chunks,
            concepts=concepts,
            entities=entities,
            tags=tags,
        )

    return wiki_ingest(
        wiki_root,
        title=title,
        body=body,
        raw_content=raw_content,
        raw_filename=file_path.name,
        concepts=concepts,
        entities=entities,
        tags=tags,
    )


# ── Ingest from folder ────────────────────────────────────────────────────────

_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "dist", "build"}
_DEFAULT_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".toml", ".json", ".txt", ".rs", ".ts", ".js", ".rb", ".go", ".java"}


def _parse_gitignore_patterns(gitignore_path: Path) -> list[str]:
    """Return non-empty, non-comment patterns from a .gitignore file."""
    patterns = []
    for line in gitignore_path.read_text(errors="replace").splitlines():
        line = line.rstrip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _matches_gitignore(rel_path: str, patterns: list[str]) -> bool:
    """Return True if rel_path matches any gitignore pattern (simplified fnmatch)."""
    import fnmatch
    parts = rel_path.replace("\\", "/").split("/")
    name = parts[-1]
    for pattern in patterns:
        # Strip leading slash for anchored patterns — treat as simple fnmatch
        clean = pattern.lstrip("/")
        if not clean:
            continue
        if fnmatch.fnmatch(name, clean):
            return True
        if fnmatch.fnmatch(rel_path, clean):
            return True
        if fnmatch.fnmatch(rel_path, f"**/{clean}"):
            return True
    return False


def wiki_ingest_folder(
    wiki_root: Path,
    *,
    folder_path: Path,
    title: str = "",
    body: str = "",
    concepts: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
    extensions: list[str] | None = None,
    respect_gitignore: bool = True,
) -> dict[str, list[Path]]:
    """Ingest a local folder recursively into the wiki. Concatenates file contents."""
    if not folder_path.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    allowed_exts = set(extensions) if extensions is not None else _DEFAULT_EXTENSIONS

    gitignore_patterns: list[str] = []
    if respect_gitignore:
        gitignore_path = folder_path / ".gitignore"
        if gitignore_path.exists():
            gitignore_patterns = _parse_gitignore_patterns(gitignore_path)

    parts: list[str] = []
    file_count = 0

    for file in sorted(folder_path.rglob("*")):
        if not file.is_file():
            continue
        # Skip junk directories
        if any(skip in file.parts for skip in _SKIP_DIRS):
            continue
        # Skip files with egg-info in path
        if any(part.endswith(".egg-info") for part in file.parts):
            continue
        # Extension filter
        if file.suffix not in allowed_exts:
            continue
        # Gitignore filter
        rel = str(file.relative_to(folder_path))
        if gitignore_patterns and _matches_gitignore(rel, gitignore_patterns):
            continue

        try:
            content = file.read_text(errors="replace")
        except OSError:
            continue

        parts.append(f"\n\n--- FILE: {rel} ---\n\n{content}\n")
        file_count += 1

    raw_content = "".join(parts).lstrip("\n")

    if not title:
        title = folder_path.name.replace("-", " ").replace("_", " ").title()
    if not body:
        body = f"Ingested from local folder: {folder_path} ({file_count} files)"

    slug = _slug(title)

    # Chunk if total size exceeds threshold
    if len(raw_content.encode()) > _RAW_CHUNK_MAX:
        chunks: list[tuple[str, str]] = []
        current_chunk: list[str] = []
        current_size = 0

        for part in parts:
            part_size = len(part.encode())
            if current_chunk and current_size + part_size > _RAW_CHUNK_MAX:
                chunk_num = len(chunks) + 1
                fname = f"{slug}-folder-{chunk_num:03d}.md"
                chunks.append((fname, "".join(current_chunk).lstrip("\n")))
                current_chunk = [part]
                current_size = part_size
            else:
                current_chunk.append(part)
                current_size += part_size

        if current_chunk:
            chunk_num = len(chunks) + 1
            fname = f"{slug}-folder-{chunk_num:03d}.md"
            chunks.append((fname, "".join(current_chunk).lstrip("\n")))

        return wiki_ingest(
            wiki_root,
            title=title,
            body=body,
            raw_files=chunks,
            concepts=concepts,
            entities=entities,
            tags=tags,
        )

    raw_filename = f"{slug}-folder.md"
    return wiki_ingest(
        wiki_root,
        title=title,
        body=body,
        raw_content=raw_content,
        raw_filename=raw_filename,
        concepts=concepts,
        entities=entities,
        tags=tags,
    )


# ── Ingest from URL ───────────────────────────────────────────────────────────

def wiki_ingest_url(
    wiki_root: Path,
    *,
    url: str,
    title: str = "",
    body: str = "",
    concepts: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, list[Path]]:
    """Fetch a URL and ingest its content into the wiki."""
    import urllib.request
    import urllib.error
    from urllib.parse import urlparse

    with urllib.request.urlopen(url) as response:
        raw_bytes = response.read()
    try:
        raw_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_content = raw_bytes.decode("latin-1")

    if not title:
        m = re.search(r"<title[^>]*>([^<]+)</title>", raw_content, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
        else:
            parsed = urlparse(url)
            title = (parsed.hostname or "") + (parsed.path.rstrip("/") or "")

    if not body:
        body = f"Ingested from URL: {url}"

    parsed = urlparse(url)
    url_slug = _slug((parsed.hostname or "") + "-" + parsed.path.strip("/").replace("/", "-"))
    raw_filename = f"{url_slug}.html"

    return wiki_ingest(
        wiki_root,
        title=title,
        body=body,
        raw_content=raw_content,
        raw_filename=raw_filename,
        concepts=concepts,
        entities=entities,
        tags=tags,
    )


# ── Query ─────────────────────────────────────────────────────────────────────

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

            # Collect searchable fields
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


# ── Raw scan ─────────────────────────────────────────────────────────────────

def wiki_scan_raw(wiki_root: Path) -> list[dict]:
    """Scan raw/ for files not yet referenced by any source page.

    Returns list of dicts: {group: str, files: [str], total_size: int}.
    Groups chunks by prefix (e.g. portal-domcap-001.md .. -017.md → group "portal-domcap").
    """
    import re

    raw_dir = wiki_root / "raw"
    if not raw_dir.exists():
        return []

    # Collect all raw refs from source pages
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

    # Find unprocessed raw files
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


# ── Lint ──────────────────────────────────────────────────────────────────────

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

    # Check for broken wikilinks and orphan pages
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

    # Orphans: pages not linked from anywhere (exclude index and log)
    for page_path in all_pages:
        if page_path.stem not in linked_slugs:
            issues["orphans"].append(str(page_path))

    # Check if index is stale
    index_path = wiki_dir / "index.md"
    if index_path.exists():
        index_mtime = index_path.stat().st_mtime
        for page_path in all_pages:
            if page_path.stat().st_mtime > index_mtime:
                issues["stale_index"].append(str(page_path))

    # Check for stub pages that need compilation (concepts and entities only)
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
            # Strip ## Related and ## Update sections
            stripped = re.split(r"\n## (?:Related|Update\b)", body)[0]
            # Strip H1 heading line
            stripped = re.sub(r"^#[^\n]*\n", "", stripped, count=1)
            stripped = stripped.strip()
            if not stripped or _stub_pattern.match(stripped):
                issues["needs_compilation"].append(str(page_path))

    return issues


# ── List pages ────────────────────────────────────────────────────────────────

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


# ── Regenerate index ──────────────────────────────────────────────────────────

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
            # First non-empty, non-heading line as summary
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


# ── Cross-referencing ─────────────────────────────────────────────────────────

def _cross_reference(wiki_dir: Path, touched_pages: list[Path]) -> int:
    """Insert bidirectional wikilinks between related pages.

    Returns count of links inserted.
    """
    registry = _build_title_registry(wiki_dir)
    all_pages = _collect_all_pages(wiki_dir)

    links_inserted = 0
    touched_set = set(touched_pages)

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

            # Does other_body mention touched page (by any of its titles/aliases)?
            touched_names = _names_for_slug(touched_slug, registry)
            if _body_mentions_any(other_body, touched_names, exclude_wikilinks=True):
                added = _ensure_related_section(other, [touched])
                links_inserted += added

            # Does touched_body mention the other page?
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
    # Strip existing wikilinks from body before searching to avoid false positives
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
        # Register the slug (filename stem)
        registry[page_path.stem.replace("-", " ")] = page_path
        registry[page_path.stem] = page_path
        # Register H1 title
        h1 = _extract_h1(text)
        if h1:
            registry[h1.lower()] = page_path
        # Register aliases
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
        # Skip self-links
        if linked == page_path:
            continue
        link_entry = f"- [[{linked.stem}]]"
        # Check for exact line match to prevent duplicates
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


# ── Log ───────────────────────────────────────────────────────────────────────

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


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_page_type(page_type: str) -> None:
    if page_type not in WIKI_PAGE_TYPES:
        raise ValueError(f"Invalid page_type {page_type!r}. Must be one of: {WIKI_PAGE_TYPES}")


def _ensure_wiki_init(wiki_root: Path) -> None:
    """Auto-initialize wiki_root if it doesn't exist."""
    if not (wiki_root / "wiki").exists():
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
