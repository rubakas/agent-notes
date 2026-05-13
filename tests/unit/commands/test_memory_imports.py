"""Verify the memory package re-exports all public symbols correctly."""
import importlib

import pytest


class TestMemoryPackageExports:
    """All do_* functions are importable from the package top level."""

    def test_vault_functions_importable(self):
        from agent_notes.commands.memory import do_vault, do_init, do_index
        assert callable(do_vault)
        assert callable(do_init)
        assert callable(do_index)

    def test_notes_functions_importable(self):
        from agent_notes.commands.memory import do_add, do_list, do_show, do_size
        assert callable(do_add)
        assert callable(do_list)
        assert callable(do_show)
        assert callable(do_size)

    def test_transfer_functions_importable(self):
        from agent_notes.commands.memory import do_export, do_import
        assert callable(do_export)
        assert callable(do_import)

    def test_wiki_functions_importable(self):
        from agent_notes.commands.memory import do_ingest, do_query, do_lint, do_scan_raw
        assert callable(do_ingest)
        assert callable(do_query)
        assert callable(do_lint)
        assert callable(do_scan_raw)

    def test_migrate_function_importable(self):
        from agent_notes.commands.memory import do_migrate
        assert callable(do_migrate)

    def test_reset_function_importable(self):
        from agent_notes.commands.memory import do_reset
        assert callable(do_reset)

    def test_all_do_functions_callable_in_one_pass(self):
        """Bulk check: every do_* re-export from the package is callable."""
        from agent_notes.commands import memory as mem
        do_functions = [
            mem.do_vault, mem.do_init, mem.do_index,
            mem.do_add, mem.do_list, mem.do_show, mem.do_size,
            mem.do_export, mem.do_import,
            mem.do_ingest, mem.do_query, mem.do_lint, mem.do_scan_raw,
            mem.do_migrate,
            mem.do_reset,
        ]
        for fn in do_functions:
            assert callable(fn), f"{fn!r} is not callable"


class TestMemorySubmodulesImportable:
    """Each submodule is independently importable without error."""

    @pytest.mark.parametrize("submodule", [
        "agent_notes.commands.memory",
        "agent_notes.commands.memory._common",
        "agent_notes.commands.memory.vault",
        "agent_notes.commands.memory.notes",
        "agent_notes.commands.memory.transfer",
        "agent_notes.commands.memory.wiki",
        "agent_notes.commands.memory.migrate",
        "agent_notes.commands.memory.reset",
    ])
    def test_submodule_importable(self, submodule):
        mod = importlib.import_module(submodule)
        assert mod is not None

    def test_common_helpers_accessible(self):
        from agent_notes.commands.memory._common import (
            _load_memory_config,
            get_directory_size,
            format_size,
            _WIKI_TYPE_MAP,
        )
        assert callable(_load_memory_config)
        assert callable(get_directory_size)
        assert callable(format_size)
        assert isinstance(_WIKI_TYPE_MAP, dict)

    def test_common_re_exported_from_package(self):
        """_common helpers are also accessible via the package namespace."""
        from agent_notes.commands.memory import (
            _load_memory_config,
            get_directory_size,
            format_size,
            _WIKI_TYPE_MAP,
        )
        assert callable(_load_memory_config)
        assert callable(get_directory_size)
        assert callable(format_size)
        assert isinstance(_WIKI_TYPE_MAP, dict)


class TestMemoryNoCircularImports:
    """Loading submodules in any order must not raise ImportError."""

    def test_no_circular_imports_on_fresh_import(self):
        """All memory submodules are importable in sequence without circular-import failure."""
        modules = [
            "agent_notes.commands.memory",
            "agent_notes.commands.memory.vault",
            "agent_notes.commands.memory.notes",
            "agent_notes.commands.memory.transfer",
            "agent_notes.commands.memory.wiki",
            "agent_notes.commands.memory.migrate",
            "agent_notes.commands.memory.reset",
        ]
        for mod_name in modules:
            # importlib.import_module is idempotent — repeated calls reuse sys.modules
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"{mod_name} returned None"
