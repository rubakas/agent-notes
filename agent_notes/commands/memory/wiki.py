"""Wiki-only subcommands: ingest, query, lint, scan_raw."""

from pathlib import Path
from typing import Optional

from . import _common
from ...config import Color


def do_scan_raw() -> None:
    """Scan raw/ for unprocessed files and print summary."""
    backend, path = _common._load_memory_config()
    if backend != "wiki":
        print("The `ingest` subcommand is only available for wiki storage.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    from ...services.wiki_backend import wiki_scan_raw
    groups = wiki_scan_raw(path)
    if not groups:
        print("No unprocessed files in raw/.")
        return
    total_files = sum(len(g["files"]) for g in groups)
    print(f"Unprocessed raw files ({total_files} files in {len(groups)} groups):\n")
    for g in groups:
        size_kb = g["total_size"] / 1024
        if size_kb >= 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"
        file_count = len(g["files"])
        if file_count == 1:
            print(f"  {Color.CYAN}{g['group']}{Color.NC}  ({size_str})")
            print(f"    {g['files'][0]}")
        else:
            print(f"  {Color.CYAN}{g['group']}{Color.NC}  ({file_count} chunks, {size_str})")
            print(f"    {g['files'][0]} .. {g['files'][-1]}")
        print()


def do_ingest(title: str, body: str, concepts: Optional[list] = None, entities: Optional[list] = None, tags: Optional[list] = None) -> None:
    """Ingest a source into the wiki backend."""
    backend, path = _common._load_memory_config()
    if backend != "wiki":
        print("The `ingest` subcommand is only available for wiki storage.")
        return
    if path is None:
        print("Memory path not configured.")
        return

    # Auto-detect folder path — route to wiki_ingest_folder for raw archiving
    candidate = Path(title).expanduser().resolve()
    if candidate.is_dir():
        from ...services.wiki_backend import wiki_ingest_folder
        folder_name = candidate.name.replace("-", " ").replace("_", " ").title()
        result = wiki_ingest_folder(
            path,
            folder_path=candidate,
            title=folder_name,
            body=body,
            concepts=concepts,
            entities=entities,
            tags=tags,
        )
        print(f"{Color.GREEN}Ingested: {folder_name}{Color.NC}")
        for p in result.get("source", []):
            print(f"  source:  {p}")
        for p in result.get("concepts", []):
            print(f"  concept: {p}")
        for p in result.get("entities", []):
            print(f"  entity:  {p}")
        return

    from ...services.wiki_backend import wiki_ingest
    result = wiki_ingest(
        path,
        title=title,
        body=body,
        concepts=concepts or [],
        entities=entities or [],
        tags=tags or [],
    )
    source_paths = result.get("source", [])
    concept_paths = result.get("concepts", [])
    entity_paths = result.get("entities", [])
    print(f"{Color.GREEN}Ingested: {title}{Color.NC}")
    for p in source_paths:
        print(f"  source:  {p}")
    for p in concept_paths:
        print(f"  concept: {p}")
    for p in entity_paths:
        print(f"  entity:  {p}")


def do_query(keyword: str) -> None:
    """Search wiki pages by keyword."""
    backend, path = _common._load_memory_config()
    if backend != "wiki":
        print("The `query` subcommand is only available for wiki storage.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    from ...services.wiki_backend import wiki_query
    results = wiki_query(path, keyword)
    if not results:
        print(f"No results found for: {keyword}")
        return
    print(f"Results for '{keyword}' ({len(results)} found):")
    print("")
    for r in results:
        print(f"  {Color.CYAN}[{r['type']}]{Color.NC} {r['title']}")
        print(f"    {r['path']}")
        if r["snippet"]:
            print(f"    ...{r['snippet']}...")
        print("")


def do_lint() -> None:
    """Check wiki health."""
    backend, path = _common._load_memory_config()
    if backend != "wiki":
        print("The `lint` subcommand is only available for wiki storage.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    from ...services.wiki_backend import wiki_lint
    issues = wiki_lint(path)
    orphans = issues.get("orphans", [])
    broken = issues.get("broken_links", [])
    stale = issues.get("stale_index", [])

    if not orphans and not broken and not stale:
        print(f"{Color.GREEN}Wiki is healthy — no issues found.{Color.NC}")
        return

    if orphans:
        print(f"{Color.YELLOW}Orphans ({len(orphans)} pages not linked from anywhere):{Color.NC}")
        for p in orphans:
            print(f"  {p}")
        print("")
    if broken:
        print(f"{Color.YELLOW}Broken links ({len(broken)}):{Color.NC}")
        for b in broken:
            print(f"  {b}")
        print("")
    if stale:
        print(f"{Color.YELLOW}Stale index ({len(stale)} pages newer than index.md):{Color.NC}")
        for s in stale:
            print(f"  {s}")
        print(f"  Run: agent-notes memory index")
