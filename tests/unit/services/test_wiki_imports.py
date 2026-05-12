"""Verify the wiki package re-exports all public symbols correctly."""
import importlib

import pytest


# All public names that must be importable from the wiki package.
_PUBLIC_NAMES = [
    "WIKI_PAGE_TYPES",
    "wiki_init",
    "wiki_write_page",
    "wiki_ingest",
    "wiki_ingest_file",
    "wiki_ingest_folder",
    "wiki_ingest_url",
    "wiki_query",
    "wiki_scan_raw",
    "wiki_regenerate_index",
    "wiki_lint",
    "wiki_list_pages",
    "_is_credential_file",
    "_cross_reference",
]

_SUBMODULES = [
    "agent_notes.services.wiki",
    "agent_notes.services.wiki._wiki_utils",
    "agent_notes.services.wiki.wiki_storage",
    "agent_notes.services.wiki.wiki_ingest",
    "agent_notes.services.wiki.wiki_query",
    "agent_notes.services.wiki.wiki_index",
    "agent_notes.services.wiki.wiki_lint",
]


class TestWikiPackageExports:
    """All public names are importable from agent_notes.services.wiki."""

    @pytest.mark.parametrize("name", _PUBLIC_NAMES)
    def test_name_importable_from_package(self, name):
        mod = importlib.import_module("agent_notes.services.wiki")
        assert hasattr(mod, name), (
            f"agent_notes.services.wiki does not export '{name}'"
        )

    def test_callable_functions(self):
        from agent_notes.services.wiki import (
            wiki_init,
            wiki_write_page,
            wiki_ingest,
            wiki_ingest_file,
            wiki_ingest_folder,
            wiki_ingest_url,
            wiki_query,
            wiki_scan_raw,
            wiki_regenerate_index,
            wiki_lint,
            wiki_list_pages,
            _is_credential_file,
            _cross_reference,
        )
        callables = [
            wiki_init, wiki_write_page,
            wiki_ingest, wiki_ingest_file, wiki_ingest_folder, wiki_ingest_url,
            wiki_query, wiki_scan_raw,
            wiki_regenerate_index,
            wiki_lint, wiki_list_pages,
            _is_credential_file, _cross_reference,
        ]
        for fn in callables:
            assert callable(fn), f"{fn!r} is not callable"


class TestWikiBackwardCompatShim:
    """All public names remain importable from the legacy wiki_backend module."""

    @pytest.mark.parametrize("name", _PUBLIC_NAMES)
    def test_name_importable_from_shim(self, name):
        mod = importlib.import_module("agent_notes.services.wiki_backend")
        assert hasattr(mod, name), (
            f"agent_notes.services.wiki_backend shim does not export '{name}'"
        )

    def test_shim_callable_functions(self):
        from agent_notes.services.wiki_backend import (
            wiki_init,
            wiki_write_page,
            wiki_ingest,
            wiki_ingest_file,
            wiki_ingest_folder,
            wiki_ingest_url,
            wiki_query,
            wiki_scan_raw,
            wiki_regenerate_index,
            wiki_lint,
            wiki_list_pages,
        )
        callables = [
            wiki_init, wiki_write_page,
            wiki_ingest, wiki_ingest_file, wiki_ingest_folder, wiki_ingest_url,
            wiki_query, wiki_scan_raw,
            wiki_regenerate_index,
            wiki_lint, wiki_list_pages,
        ]
        for fn in callables:
            assert callable(fn), f"{fn!r} is not callable"


class TestWikiSubmodulesImportable:
    """Each submodule is independently importable without error."""

    @pytest.mark.parametrize("submodule", _SUBMODULES)
    def test_submodule_importable(self, submodule):
        mod = importlib.import_module(submodule)
        assert mod is not None, f"{submodule} returned None"

    def test_wiki_storage_exports(self):
        from agent_notes.services.wiki.wiki_storage import wiki_init, wiki_write_page
        assert callable(wiki_init)
        assert callable(wiki_write_page)

    def test_wiki_ingest_exports(self):
        from agent_notes.services.wiki.wiki_ingest import (
            wiki_ingest,
            wiki_ingest_file,
            wiki_ingest_folder,
            wiki_ingest_url,
            _is_credential_file,
        )
        assert callable(wiki_ingest)
        assert callable(wiki_ingest_file)
        assert callable(wiki_ingest_folder)
        assert callable(wiki_ingest_url)
        assert callable(_is_credential_file)

    def test_wiki_query_exports(self):
        from agent_notes.services.wiki.wiki_query import wiki_query, wiki_scan_raw
        assert callable(wiki_query)
        assert callable(wiki_scan_raw)

    def test_wiki_index_exports(self):
        from agent_notes.services.wiki.wiki_index import wiki_regenerate_index, _cross_reference
        assert callable(wiki_regenerate_index)
        assert callable(_cross_reference)

    def test_wiki_lint_exports(self):
        from agent_notes.services.wiki.wiki_lint import wiki_lint, wiki_list_pages
        assert callable(wiki_lint)
        assert callable(wiki_list_pages)

    def test_wiki_utils_exports_page_types(self):
        from agent_notes.services.wiki._wiki_utils import WIKI_PAGE_TYPES
        assert isinstance(WIKI_PAGE_TYPES, list)
        assert len(WIKI_PAGE_TYPES) > 0


class TestWikiPackageAllList:
    """__all__ on the wiki package is complete and self-consistent."""

    def test_all_exists(self):
        import agent_notes.services.wiki as wiki
        assert hasattr(wiki, "__all__"), "wiki package is missing __all__"

    def test_all_names_are_resolvable(self):
        """Every name in __all__ must be an actual attribute of the package."""
        import agent_notes.services.wiki as wiki
        for name in wiki.__all__:
            assert hasattr(wiki, name), (
                f"agent_notes.services.wiki.__all__ lists '{name}' "
                f"but it is not an attribute of the package"
            )

    @pytest.mark.parametrize("name", _PUBLIC_NAMES)
    def test_public_name_in_all(self, name):
        import agent_notes.services.wiki as wiki
        assert name in wiki.__all__, (
            f"'{name}' is a documented public name but is missing from __all__"
        )


class TestWikiNoCircularImports:
    """Loading submodules in any order must not raise ImportError."""

    def test_no_circular_imports_on_sequential_import(self):
        """All wiki submodules are importable in sequence without circular-import failure."""
        for mod_name in _SUBMODULES:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"{mod_name} returned None"

    def test_shim_importable_after_package(self):
        """The backward-compat shim loads cleanly after the real package is imported."""
        importlib.import_module("agent_notes.services.wiki")
        shim = importlib.import_module("agent_notes.services.wiki_backend")
        assert shim is not None


class TestWikiPageTypesAccessibility:
    """WIKI_PAGE_TYPES is reachable from both the package and the shim."""

    def test_wiki_page_types_from_package(self):
        from agent_notes.services.wiki import WIKI_PAGE_TYPES
        assert isinstance(WIKI_PAGE_TYPES, list)
        assert len(WIKI_PAGE_TYPES) > 0

    def test_wiki_page_types_from_shim(self):
        from agent_notes.services.wiki_backend import WIKI_PAGE_TYPES
        assert isinstance(WIKI_PAGE_TYPES, list)
        assert len(WIKI_PAGE_TYPES) > 0

    def test_wiki_page_types_same_object(self):
        """Both import paths must resolve to the same list object (no duplication)."""
        from agent_notes.services.wiki import WIKI_PAGE_TYPES as from_pkg
        from agent_notes.services.wiki_backend import WIKI_PAGE_TYPES as from_shim
        assert from_pkg is from_shim

    def test_wiki_page_types_contains_expected_categories(self):
        """WIKI_PAGE_TYPES contains the standard page categories."""
        from agent_notes.services.wiki import WIKI_PAGE_TYPES
        for expected in ("sources", "concepts", "entities", "synthesis", "sessions"):
            assert expected in WIKI_PAGE_TYPES, (
                f"WIKI_PAGE_TYPES is missing expected category '{expected}'"
            )
