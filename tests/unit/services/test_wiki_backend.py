"""Tests for agent_notes.services.wiki_backend."""
import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from agent_notes.services.wiki_backend import (
    wiki_init,
    wiki_write_page,
    wiki_ingest,
    wiki_ingest_file,
    wiki_ingest_folder,
    wiki_ingest_url,
    wiki_query,
    wiki_lint,
    wiki_list_pages,
    wiki_regenerate_index,
    _cross_reference,
    WIKI_PAGE_TYPES,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    """Extract key/value pairs from YAML frontmatter block."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_block = text[3:end].strip()
    result = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


# ── wiki_init ─────────────────────────────────────────────────────────────────

class TestWikiInit:
    def test_creates_raw_directory(self, tmp_path):
        wiki_init(tmp_path)
        assert (tmp_path / "raw").is_dir()

    def test_creates_wiki_directory(self, tmp_path):
        wiki_init(tmp_path)
        assert (tmp_path / "wiki").is_dir()

    def test_creates_all_page_type_subdirectories(self, tmp_path):
        wiki_init(tmp_path)
        for sub in WIKI_PAGE_TYPES:
            assert (tmp_path / "wiki" / sub).is_dir(), f"Missing subdir: wiki/{sub}"

    def test_creates_index_md(self, tmp_path):
        wiki_init(tmp_path)
        assert (tmp_path / "wiki" / "index.md").exists()

    def test_index_md_contains_header(self, tmp_path):
        wiki_init(tmp_path)
        content = (tmp_path / "wiki" / "index.md").read_text()
        assert "wiki index" in content.lower()

    def test_creates_log_md(self, tmp_path):
        wiki_init(tmp_path)
        assert (tmp_path / "wiki" / "log.md").exists()

    def test_log_md_contains_header(self, tmp_path):
        wiki_init(tmp_path)
        content = (tmp_path / "wiki" / "log.md").read_text()
        assert "wiki log" in content.lower()

    def test_idempotent_does_not_raise_on_second_call(self, tmp_path):
        wiki_init(tmp_path)
        wiki_init(tmp_path)  # Must not raise

    def test_idempotent_does_not_overwrite_existing_index(self, tmp_path):
        wiki_init(tmp_path)
        index_path = tmp_path / "wiki" / "index.md"
        original_content = index_path.read_text()
        wiki_init(tmp_path)
        assert index_path.read_text() == original_content

    def test_idempotent_does_not_overwrite_existing_log(self, tmp_path):
        wiki_init(tmp_path)
        log_path = tmp_path / "wiki" / "log.md"
        log_path.write_text("# Wiki Log\n\nsome entries\n")
        wiki_init(tmp_path)
        assert "some entries" in log_path.read_text()


# ── wiki_write_page ───────────────────────────────────────────────────────────

class TestWikiWritePageCreate:
    def test_returns_path_to_created_file(self, tmp_path):
        path = wiki_write_page(tmp_path, title="My Page", body="content", page_type="concepts")
        assert isinstance(path, Path)
        assert path.exists()

    def test_file_placed_in_correct_subdirectory(self, tmp_path):
        path = wiki_write_page(tmp_path, title="Alpha", body="b", page_type="concepts")
        assert path.parent.name == "concepts"

    def test_file_placed_in_sources_subdirectory(self, tmp_path):
        path = wiki_write_page(tmp_path, title="My Source", body="b", page_type="sources")
        assert path.parent.name == "sources"

    def test_file_placed_in_entities_subdirectory(self, tmp_path):
        path = wiki_write_page(tmp_path, title="Alice", body="b", page_type="entities")
        assert path.parent.name == "entities"

    def test_file_placed_in_synthesis_subdirectory(self, tmp_path):
        path = wiki_write_page(tmp_path, title="Overview", body="b", page_type="synthesis")
        assert path.parent.name == "synthesis"

    def test_file_placed_in_sessions_subdirectory(self, tmp_path):
        path = wiki_write_page(tmp_path, title="Session One", body="b", page_type="sessions")
        assert path.parent.name == "sessions"

    def test_filename_is_slugified_title(self, tmp_path):
        path = wiki_write_page(tmp_path, title="Hello World", body="b", page_type="concepts")
        assert path.stem == "hello-world"

    def test_filename_has_md_extension(self, tmp_path):
        path = wiki_write_page(tmp_path, title="My Page", body="b", page_type="concepts")
        assert path.suffix == ".md"

    def test_frontmatter_starts_with_triple_dashes(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts")
        assert path.read_text().startswith("---")

    def test_frontmatter_has_created_at(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts")
        content = path.read_text()
        assert re.search(r"created_at: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)

    def test_frontmatter_has_updated_at(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts")
        content = path.read_text()
        assert re.search(r"updated_at: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)

    def test_frontmatter_has_type_field(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts")
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("type") == "concepts"

    def test_frontmatter_has_agent_when_provided(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", agent="coder")
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("agent") == "coder"

    def test_frontmatter_omits_agent_when_empty(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", agent="")
        assert "agent:" not in path.read_text()

    def test_frontmatter_has_project_when_provided(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", project="my-proj")
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("project") == "my-proj"

    def test_frontmatter_omits_project_when_empty(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", project="")
        assert "project:" not in path.read_text()

    def test_frontmatter_has_tags_when_provided(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", tags=["alpha", "beta"])
        content = path.read_text()
        assert "alpha" in content
        assert "beta" in content

    def test_frontmatter_omits_tags_when_empty(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", tags=[])
        assert "tags:" not in path.read_text()

    def test_frontmatter_has_aliases_when_provided(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", aliases=["AKA"])
        content = path.read_text()
        assert "AKA" in content

    def test_frontmatter_has_sources_when_provided(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="sources", sources=["raw/file.md"])
        content = path.read_text()
        assert "raw/file.md" in content

    def test_body_appears_under_h1_title(self, tmp_path):
        path = wiki_write_page(tmp_path, title="My Page", body="the body text", page_type="concepts")
        content = path.read_text()
        assert "# My Page" in content
        h1_pos = content.index("# My Page")
        body_pos = content.index("the body text")
        assert body_pos > h1_pos

    def test_page_has_related_section(self, tmp_path):
        path = wiki_write_page(tmp_path, title="P", body="b", page_type="concepts")
        assert "## Related" in path.read_text()

    def test_invalid_page_type_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError) as exc_info:
            wiki_write_page(tmp_path, title="P", body="b", page_type="invalid_type")
        assert "invalid_type" in str(exc_info.value).lower() or "page_type" in str(exc_info.value).lower()

    def test_auto_initializes_wiki_root_if_missing(self, tmp_path):
        root = tmp_path / "new_wiki"
        wiki_write_page(root, title="P", body="b", page_type="concepts")
        assert (root / "wiki").is_dir()


class TestWikiWritePageUpdate:
    def test_update_appends_under_update_heading(self, tmp_path):
        wiki_write_page(tmp_path, title="Note", body="original", page_type="concepts")
        wiki_write_page(tmp_path, title="Note", body="updated content", page_type="concepts")
        path = tmp_path / "wiki" / "concepts" / "note.md"
        content = path.read_text()
        assert "## Update" in content
        assert "updated content" in content

    def test_update_preserves_original_body(self, tmp_path):
        wiki_write_page(tmp_path, title="Note", body="original content", page_type="concepts")
        wiki_write_page(tmp_path, title="Note", body="new content", page_type="concepts")
        path = tmp_path / "wiki" / "concepts" / "note.md"
        content = path.read_text()
        assert "original content" in content

    def test_update_changes_updated_at(self, tmp_path):
        import time
        path = wiki_write_page(tmp_path, title="Note", body="v1", page_type="concepts")
        first_content = path.read_text()
        first_fm = _parse_frontmatter(first_content)
        time.sleep(1.1)
        wiki_write_page(tmp_path, title="Note", body="v2", page_type="concepts")
        second_content = path.read_text()
        second_fm = _parse_frontmatter(second_content)
        assert second_fm.get("updated_at") >= first_fm.get("updated_at")

    def test_update_preserves_created_at(self, tmp_path):
        import time
        path = wiki_write_page(tmp_path, title="Note", body="v1", page_type="concepts")
        fm_first = _parse_frontmatter(path.read_text())
        created_at_first = fm_first.get("created_at")
        time.sleep(1.1)
        wiki_write_page(tmp_path, title="Note", body="v2", page_type="concepts")
        fm_second = _parse_frontmatter(path.read_text())
        assert fm_second.get("created_at") == created_at_first

    def test_update_merges_new_tags_into_existing(self, tmp_path):
        wiki_write_page(tmp_path, title="Note", body="b", page_type="concepts", tags=["old"])
        wiki_write_page(tmp_path, title="Note", body="b", page_type="concepts", tags=["new"])
        path = tmp_path / "wiki" / "concepts" / "note.md"
        content = path.read_text()
        assert "old" in content
        assert "new" in content

    def test_update_does_not_duplicate_existing_tags(self, tmp_path):
        wiki_write_page(tmp_path, title="Note", body="b", page_type="concepts", tags=["alpha"])
        wiki_write_page(tmp_path, title="Note", body="b", page_type="concepts", tags=["alpha"])
        path = tmp_path / "wiki" / "concepts" / "note.md"
        content = path.read_text()
        # alpha should appear in the tags list exactly once
        fm_block = content.split("---")[1]
        assert fm_block.count("alpha") == 1

    def test_update_merges_new_aliases(self, tmp_path):
        wiki_write_page(tmp_path, title="Note", body="b", page_type="concepts", aliases=["First"])
        wiki_write_page(tmp_path, title="Note", body="b", page_type="concepts", aliases=["Second"])
        path = tmp_path / "wiki" / "concepts" / "note.md"
        content = path.read_text()
        assert "First" in content
        assert "Second" in content

    def test_update_heading_contains_timestamp(self, tmp_path):
        wiki_write_page(tmp_path, title="Note", body="v1", page_type="concepts")
        wiki_write_page(tmp_path, title="Note", body="v2", page_type="concepts")
        path = tmp_path / "wiki" / "concepts" / "note.md"
        content = path.read_text()
        assert re.search(r"## Update \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)


# ── wiki_ingest ───────────────────────────────────────────────────────────────

class TestWikiIngest:
    def test_returns_dict_with_source_key(self, tmp_path):
        result = wiki_ingest(tmp_path, title="My Source", body="summary")
        assert "source" in result

    def test_returns_dict_with_concepts_key(self, tmp_path):
        result = wiki_ingest(tmp_path, title="My Source", body="summary")
        assert "concepts" in result

    def test_returns_dict_with_entities_key(self, tmp_path):
        result = wiki_ingest(tmp_path, title="My Source", body="summary")
        assert "entities" in result

    def test_source_path_is_in_sources_directory(self, tmp_path):
        result = wiki_ingest(tmp_path, title="My Source", body="summary")
        source_path = result["source"][0]
        assert source_path.parent.name == "sources"

    def test_stores_raw_content_in_raw_directory(self, tmp_path):
        wiki_ingest(
            tmp_path,
            title="My Source",
            body="summary",
            raw_content="raw text here",
            raw_filename="my-source.md",
        )
        raw_file = tmp_path / "raw" / "my-source.md"
        assert raw_file.exists()
        assert "raw text here" in raw_file.read_text()

    def test_raw_filename_defaults_to_slugified_title(self, tmp_path):
        wiki_ingest(tmp_path, title="Auto Raw Name", body="summary", raw_content="raw data")
        raw_file = tmp_path / "raw" / "auto-raw-name.md"
        assert raw_file.exists()

    def test_source_page_references_raw_file_in_frontmatter(self, tmp_path):
        result = wiki_ingest(
            tmp_path,
            title="My Source",
            body="summary",
            raw_content="raw text",
            raw_filename="my-source.md",
        )
        source_path = result["source"][0]
        content = source_path.read_text()
        assert "raw/my-source.md" in content

    def test_creates_concept_pages_for_each_concept(self, tmp_path):
        result = wiki_ingest(
            tmp_path, title="S", body="b", concepts=["Concept A", "Concept B"]
        )
        assert len(result["concepts"]) == 2

    def test_concept_pages_placed_in_concepts_directory(self, tmp_path):
        result = wiki_ingest(tmp_path, title="S", body="b", concepts=["My Concept"])
        assert result["concepts"][0].parent.name == "concepts"

    def test_creates_entity_pages_for_each_entity(self, tmp_path):
        result = wiki_ingest(
            tmp_path, title="S", body="b", entities=["Alice", "Bob"]
        )
        assert len(result["entities"]) == 2

    def test_entity_pages_placed_in_entities_directory(self, tmp_path):
        result = wiki_ingest(tmp_path, title="S", body="b", entities=["Alice"])
        assert result["entities"][0].parent.name == "entities"

    def test_works_with_empty_concepts_list(self, tmp_path):
        result = wiki_ingest(tmp_path, title="S", body="b", concepts=[])
        assert result["concepts"] == []

    def test_works_with_empty_entities_list(self, tmp_path):
        result = wiki_ingest(tmp_path, title="S", body="b", entities=[])
        assert result["entities"] == []

    def test_works_with_no_raw_content(self, tmp_path):
        result = wiki_ingest(tmp_path, title="S", body="summary")
        assert len(result["source"]) == 1
        assert not any((tmp_path / "raw").glob("*"))

    def test_concept_page_body_references_source(self, tmp_path):
        result = wiki_ingest(tmp_path, title="My Source", body="b", concepts=["Alpha Concept"])
        concept_content = result["concepts"][0].read_text()
        # Should reference the source in the body
        assert "my-source" in concept_content or "My Source" in concept_content

    def test_tags_propagated_to_source_and_concept_pages(self, tmp_path):
        result = wiki_ingest(
            tmp_path, title="S", body="b", concepts=["C"], tags=["shared-tag"]
        )
        source_content = result["source"][0].read_text()
        concept_content = result["concepts"][0].read_text()
        assert "shared-tag" in source_content
        assert "shared-tag" in concept_content

    def test_auto_initializes_wiki_root_if_missing(self, tmp_path):
        root = tmp_path / "new_wiki"
        wiki_ingest(root, title="S", body="b")
        assert (root / "wiki").is_dir()


# ── wiki_query ────────────────────────────────────────────────────────────────

class TestWikiQuery:
    def test_finds_page_by_title_match(self, tmp_path):
        wiki_write_page(tmp_path, title="Python Basics", body="intro", page_type="concepts")
        results = wiki_query(tmp_path, "Python Basics")
        assert any("Python Basics" in r["title"] for r in results)

    def test_finds_page_by_partial_title_match(self, tmp_path):
        wiki_write_page(tmp_path, title="Deep Learning", body="intro", page_type="concepts")
        results = wiki_query(tmp_path, "learning")
        assert len(results) >= 1

    def test_finds_page_by_tag_match(self, tmp_path):
        wiki_write_page(tmp_path, title="P", body="body", page_type="concepts", tags=["ml", "ai"])
        results = wiki_query(tmp_path, "ml")
        assert len(results) >= 1

    def test_finds_page_by_alias_match(self, tmp_path):
        wiki_write_page(tmp_path, title="Neural Network", body="b", page_type="concepts", aliases=["NN"])
        results = wiki_query(tmp_path, "NN")
        assert len(results) >= 1

    def test_finds_page_by_body_text_match(self, tmp_path):
        wiki_write_page(tmp_path, title="P", body="backpropagation algorithm", page_type="concepts")
        results = wiki_query(tmp_path, "backpropagation")
        assert len(results) >= 1

    def test_returns_empty_list_for_no_matches(self, tmp_path):
        wiki_write_page(tmp_path, title="P", body="b", page_type="concepts")
        results = wiki_query(tmp_path, "xyzzy_no_match_12345")
        assert results == []

    def test_case_insensitive_title_match(self, tmp_path):
        wiki_write_page(tmp_path, title="Python Basics", body="intro", page_type="concepts")
        results = wiki_query(tmp_path, "python basics")
        assert len(results) >= 1

    def test_case_insensitive_body_match(self, tmp_path):
        wiki_write_page(tmp_path, title="P", body="TensorFlow Framework", page_type="concepts")
        results = wiki_query(tmp_path, "tensorflow")
        assert len(results) >= 1

    def test_result_has_required_fields(self, tmp_path):
        wiki_write_page(tmp_path, title="MyPage", body="some content", page_type="concepts")
        results = wiki_query(tmp_path, "some content")
        assert len(results) >= 1
        r = results[0]
        assert "path" in r
        assert "title" in r
        assert "type" in r
        assert "snippet" in r

    def test_result_type_matches_page_type(self, tmp_path):
        wiki_write_page(tmp_path, title="Alice", body="entity", page_type="entities")
        results = wiki_query(tmp_path, "Alice")
        assert any(r["type"] == "entities" for r in results)

    def test_returns_empty_list_when_wiki_root_missing(self, tmp_path):
        results = wiki_query(tmp_path / "nonexistent", "anything")
        assert results == []

    def test_searches_across_multiple_page_types(self, tmp_path):
        wiki_write_page(tmp_path, title="Shared Keyword Source", body="unique-term", page_type="sources")
        wiki_write_page(tmp_path, title="Shared Keyword Concept", body="unique-term", page_type="concepts")
        results = wiki_query(tmp_path, "unique-term")
        types_found = {r["type"] for r in results}
        assert "sources" in types_found
        assert "concepts" in types_found


# ── wiki_lint ─────────────────────────────────────────────────────────────────

class TestWikiLint:
    def test_returns_dict_with_orphans_key(self, tmp_path):
        wiki_init(tmp_path)
        result = wiki_lint(tmp_path)
        assert "orphans" in result

    def test_returns_dict_with_broken_links_key(self, tmp_path):
        wiki_init(tmp_path)
        result = wiki_lint(tmp_path)
        assert "broken_links" in result

    def test_returns_dict_with_stale_index_key(self, tmp_path):
        wiki_init(tmp_path)
        result = wiki_lint(tmp_path)
        assert "stale_index" in result

    def test_empty_wiki_returns_empty_lists(self, tmp_path):
        wiki_init(tmp_path)
        result = wiki_lint(tmp_path)
        assert result["broken_links"] == []

    def test_detects_broken_wikilinks(self, tmp_path):
        wiki_init(tmp_path)
        page = tmp_path / "wiki" / "concepts" / "my-page.md"
        page.write_text("---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# My Page\n\nSee [[nonexistent-page]].\n\n## Related\n\n")
        result = wiki_lint(tmp_path)
        assert any("nonexistent-page" in entry for entry in result["broken_links"])

    def test_no_broken_links_when_target_exists(self, tmp_path):
        wiki_write_page(tmp_path, title="Target Page", body="content", page_type="concepts")
        source = tmp_path / "wiki" / "concepts" / "source-page.md"
        source.write_text("---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Source Page\n\nSee [[target-page]].\n\n## Related\n\n")
        result = wiki_lint(tmp_path)
        broken = [b for b in result["broken_links"] if "target-page" in b]
        assert broken == []

    def test_detects_orphan_pages(self, tmp_path):
        wiki_write_page(tmp_path, title="Lonely Page", body="no one links here", page_type="concepts")
        result = wiki_lint(tmp_path)
        # Orphans: pages not linked from any other page
        assert any("lonely-page" in orphan for orphan in result["orphans"])

    def test_returns_empty_dict_when_wiki_root_missing(self, tmp_path):
        result = wiki_lint(tmp_path / "nonexistent")
        assert result["orphans"] == []
        assert result["broken_links"] == []
        assert result["stale_index"] == []


# ── wiki_list_pages ───────────────────────────────────────────────────────────

class TestWikiListPages:
    def test_returns_list(self, tmp_path):
        wiki_init(tmp_path)
        result = wiki_list_pages(tmp_path)
        assert isinstance(result, list)

    def test_returns_empty_list_for_empty_wiki(self, tmp_path):
        wiki_init(tmp_path)
        result = wiki_list_pages(tmp_path)
        assert result == []

    def test_returns_entry_for_each_page(self, tmp_path):
        wiki_write_page(tmp_path, title="Page A", body="b", page_type="concepts")
        wiki_write_page(tmp_path, title="Page B", body="b", page_type="entities")
        result = wiki_list_pages(tmp_path)
        assert len(result) == 2

    def test_each_entry_has_required_fields(self, tmp_path):
        wiki_write_page(tmp_path, title="My Page", body="b", page_type="concepts")
        result = wiki_list_pages(tmp_path)
        assert len(result) == 1
        entry = result[0]
        assert "type" in entry
        assert "file" in entry
        assert "path" in entry
        assert "title" in entry
        assert "tags" in entry
        assert "updated_at" in entry

    def test_entry_type_matches_page_type(self, tmp_path):
        wiki_write_page(tmp_path, title="Ent", body="b", page_type="entities")
        result = wiki_list_pages(tmp_path)
        assert result[0]["type"] == "entities"

    def test_entry_title_matches_h1(self, tmp_path):
        wiki_write_page(tmp_path, title="My Title", body="b", page_type="concepts")
        result = wiki_list_pages(tmp_path)
        assert result[0]["title"] == "My Title"

    def test_entry_tags_matches_page_tags(self, tmp_path):
        wiki_write_page(tmp_path, title="Tagged", body="b", page_type="concepts", tags=["foo", "bar"])
        result = wiki_list_pages(tmp_path)
        assert "foo" in result[0]["tags"]
        assert "bar" in result[0]["tags"]

    def test_returns_empty_list_when_wiki_root_missing(self, tmp_path):
        result = wiki_list_pages(tmp_path / "nonexistent")
        assert result == []

    def test_lists_pages_from_all_page_types(self, tmp_path):
        wiki_write_page(tmp_path, title="C", body="b", page_type="concepts")
        wiki_write_page(tmp_path, title="E", body="b", page_type="entities")
        wiki_write_page(tmp_path, title="S", body="b", page_type="sources")
        result = wiki_list_pages(tmp_path)
        types = {r["type"] for r in result}
        assert "concepts" in types
        assert "entities" in types
        assert "sources" in types


# ── wiki_regenerate_index ─────────────────────────────────────────────────────

class TestWikiRegenerateIndex:
    def test_creates_or_updates_index_md(self, tmp_path):
        wiki_init(tmp_path)
        wiki_regenerate_index(tmp_path)
        assert (tmp_path / "wiki" / "index.md").exists()

    def test_index_contains_wiki_index_header(self, tmp_path):
        wiki_init(tmp_path)
        wiki_regenerate_index(tmp_path)
        content = (tmp_path / "wiki" / "index.md").read_text()
        assert "wiki index" in content.lower()

    def test_index_lists_page_with_wikilink(self, tmp_path):
        wiki_write_page(tmp_path, title="Concept Alpha", body="b", page_type="concepts")
        content = (tmp_path / "wiki" / "index.md").read_text()
        assert "[[concept-alpha]]" in content

    def test_index_groups_pages_by_type(self, tmp_path):
        wiki_write_page(tmp_path, title="My Concept", body="b", page_type="concepts")
        wiki_write_page(tmp_path, title="My Entity", body="b", page_type="entities")
        content = (tmp_path / "wiki" / "index.md").read_text()
        # The index should have sections for both types
        assert "concepts" in content.lower()
        assert "entities" in content.lower()

    def test_index_shows_page_count_per_section(self, tmp_path):
        wiki_write_page(tmp_path, title="C1", body="b", page_type="concepts")
        wiki_write_page(tmp_path, title="C2", body="b", page_type="concepts")
        content = (tmp_path / "wiki" / "index.md").read_text()
        # Should show count like "Concepts (2)"
        assert re.search(r"concepts.*\(2\)", content, re.IGNORECASE)

    def test_index_skips_empty_categories(self, tmp_path):
        wiki_write_page(tmp_path, title="C", body="b", page_type="concepts")
        content = (tmp_path / "wiki" / "index.md").read_text()
        # synthesis was never written, should not appear as a header
        assert "## Synthesis" not in content

    def test_index_includes_updated_date(self, tmp_path):
        wiki_write_page(tmp_path, title="P", body="b", page_type="concepts", tags=[])
        content = (tmp_path / "wiki" / "index.md").read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}", content)

    def test_index_includes_tags_in_row(self, tmp_path):
        wiki_write_page(tmp_path, title="Tagged Page", body="b", page_type="concepts", tags=["mytag"])
        content = (tmp_path / "wiki" / "index.md").read_text()
        assert "mytag" in content

    def test_index_regenerated_after_new_page(self, tmp_path):
        wiki_write_page(tmp_path, title="First", body="b", page_type="concepts")
        wiki_write_page(tmp_path, title="Second", body="b", page_type="concepts")
        content = (tmp_path / "wiki" / "index.md").read_text()
        assert "first" in content
        assert "second" in content


# ── _cross_reference ──────────────────────────────────────────────────────────

class TestCrossReference:
    def test_adds_link_when_body_mentions_another_page_title(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        # Create page A
        page_a = wiki_dir / "concepts" / "page-a.md"
        page_a.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Page A\n\nThis mentions page b.\n\n## Related\n\n"
        )
        # Create page B
        page_b = wiki_dir / "concepts" / "page-b.md"
        page_b.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Page B\n\nContent here.\n\n## Related\n\n"
        )

        _cross_reference(wiki_dir, [page_a])
        content_a = page_a.read_text()
        assert "[[page-b]]" in content_a

    def test_bidirectional_links_added(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        page_a = wiki_dir / "concepts" / "alpha.md"
        page_a.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Alpha\n\nMentions beta topic.\n\n## Related\n\n"
        )
        page_b = wiki_dir / "concepts" / "beta.md"
        page_b.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Beta\n\nContent about alpha topic.\n\n## Related\n\n"
        )

        _cross_reference(wiki_dir, [page_a, page_b])
        assert "[[beta]]" in page_a.read_text()
        assert "[[alpha]]" in page_b.read_text()

    def test_idempotent_does_not_duplicate_links(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        page_a = wiki_dir / "concepts" / "node-a.md"
        page_a.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Node A\n\nMentions node b.\n\n## Related\n\n"
        )
        page_b = wiki_dir / "concepts" / "node-b.md"
        page_b.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Node B\n\nContent.\n\n## Related\n\n"
        )

        _cross_reference(wiki_dir, [page_a])
        _cross_reference(wiki_dir, [page_a])
        content = page_a.read_text()
        assert content.count("[[node-b]]") == 1

    def test_no_self_reference(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        page = wiki_dir / "concepts" / "self-ref.md"
        page.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Self Ref\n\nself ref content.\n\n## Related\n\n"
        )
        _cross_reference(wiki_dir, [page])
        content = page.read_text()
        # Should not link to itself
        assert content.count("[[self-ref]]") == 0

    def test_returns_count_of_links_inserted(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        page_a = wiki_dir / "concepts" / "link-source.md"
        page_a.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Link Source\n\nMentions link target here.\n\n## Related\n\n"
        )
        page_b = wiki_dir / "concepts" / "link-target.md"
        page_b.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Link Target\n\nContent.\n\n## Related\n\n"
        )
        count = _cross_reference(wiki_dir, [page_a])
        assert count >= 1

    def test_no_link_when_body_does_not_mention_other_page(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        page_a = wiki_dir / "concepts" / "unrelated-a.md"
        page_a.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Unrelated A\n\nCompletely different content.\n\n## Related\n\n"
        )
        page_b = wiki_dir / "concepts" / "unrelated-b.md"
        page_b.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Unrelated B\n\nAlso different.\n\n## Related\n\n"
        )
        _cross_reference(wiki_dir, [page_a])
        assert "[[unrelated-b]]" not in page_a.read_text()

    def test_handles_page_with_no_body_text(self, tmp_path):
        wiki_init(tmp_path)
        wiki_dir = tmp_path / "wiki"

        empty_page = wiki_dir / "concepts" / "empty-body.md"
        empty_page.write_text(
            "---\ncreated_at: 2026-01-01T00:00:00Z\nupdated_at: 2026-01-01T00:00:00Z\ntype: concepts\n---\n\n# Empty Body\n\n"
        )
        # Should not raise
        _cross_reference(wiki_dir, [empty_page])


# ── Integration scenarios ─────────────────────────────────────────────────────

class TestWikiIntegration:
    def test_full_ingest_creates_raw_source_and_fanout_pages(self, tmp_path):
        result = wiki_ingest(
            tmp_path,
            title="Research Paper",
            body="Summary of the paper on transformers.",
            raw_content="Full paper content...",
            raw_filename="research-paper.md",
            concepts=["Transformer Architecture", "Self Attention"],
            entities=["Vaswani et al"],
            tags=["nlp", "transformers"],
        )
        # Raw file
        assert (tmp_path / "raw" / "research-paper.md").exists()
        # Source page
        assert len(result["source"]) == 1
        assert result["source"][0].parent.name == "sources"
        # Concepts
        assert len(result["concepts"]) == 2
        # Entities
        assert len(result["entities"]) == 1

    def test_write_and_query_round_trip(self, tmp_path):
        wiki_write_page(
            tmp_path,
            title="Gradient Descent",
            body="An optimization algorithm used in machine learning.",
            page_type="concepts",
            tags=["optimization", "ml"],
        )
        results = wiki_query(tmp_path, "optimization algorithm")
        assert len(results) >= 1
        assert any("Gradient Descent" in r["title"] for r in results)

    def test_log_updated_after_write_page(self, tmp_path):
        wiki_write_page(tmp_path, title="Logged Page", body="content", page_type="concepts")
        log_content = (tmp_path / "wiki" / "log.md").read_text()
        assert "Logged Page" in log_content

    def test_log_updated_after_ingest(self, tmp_path):
        wiki_ingest(tmp_path, title="Ingested Source", body="summary")
        log_content = (tmp_path / "wiki" / "log.md").read_text()
        assert "Ingested Source" in log_content

    def test_multiple_ingests_cross_reference_each_other(self, tmp_path):
        # First ingest: source that mentions "network"
        wiki_ingest(
            tmp_path,
            title="Network Overview",
            body="Overview of neural network concepts.",
            concepts=["Neural Network"],
        )
        # Second ingest: concept that mentions "network overview"
        wiki_ingest(
            tmp_path,
            title="Deep Dive",
            body="Deeper look at network overview topic.",
            concepts=["Backprop"],
        )
        # The index should reflect both sources
        index_content = (tmp_path / "wiki" / "index.md").read_text()
        assert "network-overview" in index_content
        assert "deep-dive" in index_content

    def test_write_page_updates_index_immediately(self, tmp_path):
        wiki_write_page(tmp_path, title="New Concept", body="b", page_type="concepts")
        index_content = (tmp_path / "wiki" / "index.md").read_text()
        assert "new-concept" in index_content

    def test_list_pages_reflects_all_ingested_content(self, tmp_path):
        wiki_ingest(
            tmp_path,
            title="Source One",
            body="b",
            concepts=["Concept X"],
            entities=["Entity Y"],
        )
        pages = wiki_list_pages(tmp_path)
        titles = [p["title"] for p in pages]
        assert "Source One" in titles
        assert "Concept X" in titles
        assert "Entity Y" in titles

    def test_query_after_ingest_finds_concept_pages(self, tmp_path):
        wiki_ingest(
            tmp_path,
            title="ML Overview",
            body="b",
            concepts=["Backpropagation"],
            tags=["ml"],
        )
        results = wiki_query(tmp_path, "Backpropagation")
        assert len(results) >= 1
        assert any(r["type"] == "concepts" for r in results)


# ── wiki_ingest_file ──────────────────────────────────────────────────────────

class TestWikiIngestFile:
    def test_reads_file_and_stores_as_raw_content(self, tmp_path):
        src = tmp_path / "notes.txt"
        src.write_text("hello from the file")
        wiki_ingest_file(tmp_path, file_path=src)
        raw_files = list((tmp_path / "raw").glob("*"))
        assert len(raw_files) == 1
        assert "hello from the file" in raw_files[0].read_text()

    def test_derives_title_from_filename_when_not_provided(self, tmp_path):
        src = tmp_path / "my-cool-note.txt"
        src.write_text("content")
        result = wiki_ingest_file(tmp_path, file_path=src)
        source_content = result["source"][0].read_text()
        assert "My Cool Note" in source_content

    def test_uses_provided_title_over_filename(self, tmp_path):
        src = tmp_path / "irrelevant-name.txt"
        src.write_text("content")
        result = wiki_ingest_file(tmp_path, file_path=src, title="Custom Title")
        source_content = result["source"][0].read_text()
        assert "Custom Title" in source_content

    def test_uses_file_name_as_raw_filename(self, tmp_path):
        src = tmp_path / "original.md"
        src.write_text("data")
        wiki_ingest_file(tmp_path, file_path=src)
        assert (tmp_path / "raw" / "original.md").exists()

    def test_passes_concepts_and_entities_to_wiki_ingest(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("text")
        result = wiki_ingest_file(
            tmp_path,
            file_path=src,
            concepts=["Alpha"],
            entities=["Bob"],
        )
        assert len(result["concepts"]) == 1
        assert len(result["entities"]) == 1

    def test_raises_on_nonexistent_file(self, tmp_path):
        missing = tmp_path / "ghost.txt"
        with pytest.raises((FileNotFoundError, OSError)):
            wiki_ingest_file(tmp_path, file_path=missing)

    def test_default_body_mentions_file_path(self, tmp_path):
        src = tmp_path / "myfile.txt"
        src.write_text("data")
        result = wiki_ingest_file(tmp_path, file_path=src)
        source_content = result["source"][0].read_text()
        assert "myfile.txt" in source_content


# ── wiki_ingest_folder ────────────────────────────────────────────────────────

class TestWikiIngestFolder:
    def test_ingests_all_matching_files_in_folder(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        (folder / "a.py").write_text("print('a')")
        (folder / "b.py").write_text("print('b')")
        wiki_root = tmp_path / "wiki_root"
        result = wiki_ingest_folder(wiki_root, folder_path=folder)
        raw_files = list((wiki_root / "raw").glob("*"))
        raw_content = raw_files[0].read_text()
        assert "print('a')" in raw_content
        assert "print('b')" in raw_content

    def test_skips_pycache_and_git_dirs(self, tmp_path):
        folder = tmp_path / "project"
        pycache = folder / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "cached.py").write_text("cached")
        git_dir = folder / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "config").write_text("gitconfig")
        (folder / "real.py").write_text("real code")
        wiki_root = tmp_path / "wiki_root"
        wiki_ingest_folder(wiki_root, folder_path=folder)
        raw_content = (wiki_root / "raw").glob("*")
        content = next(raw_content).read_text()
        assert "cached" not in content
        assert "gitconfig" not in content
        assert "real code" in content

    def test_respects_extension_filter(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        (folder / "script.py").write_text("python code")
        (folder / "image.png").write_text("binary data")
        wiki_root = tmp_path / "wiki_root"
        wiki_ingest_folder(wiki_root, folder_path=folder)
        raw_file = next((wiki_root / "raw").glob("*"))
        content = raw_file.read_text()
        assert "python code" in content
        assert "binary data" not in content

    def test_custom_extensions_override_defaults(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        (folder / "notes.md").write_text("markdown notes")
        (folder / "data.csv").write_text("csv data")
        wiki_root = tmp_path / "wiki_root"
        wiki_ingest_folder(wiki_root, folder_path=folder, extensions=[".csv"])
        raw_file = next((wiki_root / "raw").glob("*"))
        content = raw_file.read_text()
        assert "csv data" in content
        assert "markdown notes" not in content

    def test_concatenates_files_with_path_headers(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        (folder / "alpha.py").write_text("alpha code")
        wiki_root = tmp_path / "wiki_root"
        wiki_ingest_folder(wiki_root, folder_path=folder)
        raw_file = next((wiki_root / "raw").glob("*"))
        content = raw_file.read_text()
        assert "--- FILE:" in content
        assert "alpha.py" in content

    def test_derives_title_from_folder_name(self, tmp_path):
        folder = tmp_path / "my-project"
        folder.mkdir()
        (folder / "f.py").write_text("x")
        wiki_root = tmp_path / "wiki_root"
        result = wiki_ingest_folder(wiki_root, folder_path=folder)
        source_content = result["source"][0].read_text()
        assert "My Project" in source_content

    def test_respects_gitignore_patterns(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        (folder / ".gitignore").write_text("secret.txt\n")
        (folder / "secret.txt").write_text("do not ingest this")
        (folder / "public.py").write_text("ingest this")
        wiki_root = tmp_path / "wiki_root"
        wiki_ingest_folder(wiki_root, folder_path=folder, respect_gitignore=True)
        raw_file = next((wiki_root / "raw").glob("*"))
        content = raw_file.read_text()
        assert "do not ingest this" not in content
        assert "ingest this" in content

    def test_empty_folder_still_creates_source_page(self, tmp_path):
        folder = tmp_path / "empty-project"
        folder.mkdir()
        wiki_root = tmp_path / "wiki_root"
        result = wiki_ingest_folder(wiki_root, folder_path=folder)
        assert len(result["source"]) == 1
        assert result["source"][0].exists()

    def test_nonexistent_folder_raises(self, tmp_path):
        missing = tmp_path / "no-such-folder"
        wiki_root = tmp_path / "wiki_root"
        with pytest.raises(FileNotFoundError, match="Folder not found"):
            wiki_ingest_folder(wiki_root, folder_path=missing)


# ── wiki_ingest_url ───────────────────────────────────────────────────────────

def _make_mock_response(content: str, encoding: str = "utf-8") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = content.encode(encoding)
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestWikiIngestUrl:
    def test_fetches_url_and_stores_content(self, tmp_path):
        html = "<html><body>page content</body></html>"
        mock_resp = _make_mock_response(html)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            wiki_ingest_url(tmp_path, url="http://example.com/page")
        raw_files = list((tmp_path / "raw").glob("*"))
        assert len(raw_files) == 1
        assert "page content" in raw_files[0].read_text()

    def test_extracts_title_from_html_title_tag(self, tmp_path):
        html = "<html><head><title>My Page Title</title></head><body>body</body></html>"
        mock_resp = _make_mock_response(html)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = wiki_ingest_url(tmp_path, url="http://example.com/page")
        source_content = result["source"][0].read_text()
        assert "My Page Title" in source_content

    def test_falls_back_to_url_for_title_when_no_html_title(self, tmp_path):
        html = "<html><body>no title tag here</body></html>"
        mock_resp = _make_mock_response(html)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = wiki_ingest_url(tmp_path, url="http://example.com/some/path")
        source_content = result["source"][0].read_text()
        assert "example.com" in source_content

    def test_uses_provided_title_over_extracted(self, tmp_path):
        html = "<html><head><title>HTML Title</title></head><body>body</body></html>"
        mock_resp = _make_mock_response(html)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = wiki_ingest_url(tmp_path, url="http://example.com/", title="Override Title")
        source_content = result["source"][0].read_text()
        assert "Override Title" in source_content
        assert "HTML Title" not in source_content

    def test_stores_fetched_content_as_raw(self, tmp_path):
        html = "<html><body>raw stored content</body></html>"
        mock_resp = _make_mock_response(html)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            wiki_ingest_url(tmp_path, url="http://example.com/doc")
        raw_files = list((tmp_path / "raw").glob("*.html"))
        assert len(raw_files) == 1
        assert "raw stored content" in raw_files[0].read_text()

    def test_handles_fetch_error(self, tmp_path):
        with patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
            with pytest.raises(URLError):
                wiki_ingest_url(tmp_path, url="http://unreachable.example.com/")
