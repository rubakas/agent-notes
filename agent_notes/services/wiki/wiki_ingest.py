"""File, folder, and URL ingestion into the wiki."""

from __future__ import annotations

import fnmatch as _fnmatch
import re
from pathlib import Path

from ._wiki_utils import (
    _RAW_CHUNK_MAX,
    _atomic_write,
    _content_hash,
    _ensure_wiki_init,
    _log_operation,
)
from .._memory_utils import _slug
from .wiki_index import _cross_reference, wiki_regenerate_index
from .wiki_storage import wiki_write_page


_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "dist", "build"}
_DEFAULT_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".toml", ".json", ".txt", ".rs", ".ts", ".js", ".rb", ".go", ".java"}

_CREDENTIAL_PATTERNS = [
    ".env", ".env.*",
    "*.key", "*.pem", "*.p12", "*.pfx", "*.jks",
    "*.keystore", "*.truststore",
    "credentials.*", "secrets.*", "*-secrets.*",
    "service-account*.json",
    "*secret*.yaml", "*secret*.yml", "*secret*.json",
    "*apikey*.*", "*api-key*.*", "*api_key*.*",
    "*private-key*.*", "*private_key*.*",
]


def _is_credential_file(path: Path) -> bool:
    """Return True if the file matches known credential patterns."""
    name = path.name.lower()
    for pattern in _CREDENTIAL_PATTERNS:
        if _fnmatch.fnmatch(name, pattern):
            return True
    return False


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

    raw_refs: list[str] = []
    raw_hash = ""
    if raw_files:
        hash_parts = []
        for fname, fcontent in raw_files:
            raw_path = wiki_root / "raw" / fname
            _atomic_write(raw_path, fcontent)
            raw_refs.append(f"raw/{fname}")
            hash_parts.append(fcontent)
        raw_hash = _content_hash("".join(hash_parts))
    elif raw_content:
        if not raw_filename:
            raw_filename = f"{_slug(title)}.md"
        raw_path = wiki_root / "raw" / raw_filename
        _atomic_write(raw_path, raw_content)
        raw_refs.append(f"raw/{raw_filename}")
        raw_hash = _content_hash(raw_content)

    source_path = wiki_write_page(
        wiki_root,
        title=title,
        body=body,
        page_type="sources",
        tags=tags or [],
        sources=raw_refs if raw_refs else [],
        confidence=confidence,
        content_hash=raw_hash,
    )
    result["source"].append(source_path)

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
    if _is_credential_file(file_path):
        raise ValueError(
            f"Refusing to ingest credential file: {file_path.name}. "
            "Credential files must never be stored in the knowledge base."
        )
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
        if any(skip in file.parts for skip in _SKIP_DIRS):
            continue
        if any(part.endswith(".egg-info") for part in file.parts):
            continue
        if file.suffix not in allowed_exts:
            continue
        rel = str(file.relative_to(folder_path))
        if gitignore_patterns and _matches_gitignore(rel, gitignore_patterns):
            continue
        if _is_credential_file(file):
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
