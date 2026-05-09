"""Validate that all deferred imports in the diagnostics subsystem resolve correctly.

Deferred imports (imports inside function bodies) only crash at runtime when the
function is actually called — not at module load time. This test suite uses AST
parsing to extract every deferred import statement from _checks.py, _display.py,
and _fix.py, converts relative imports to absolute module paths, and asserts each
one is importable without ModuleNotFoundError.
"""
import ast
import importlib
import textwrap
from pathlib import Path
from typing import List, Tuple

import pytest

# ---------------------------------------------------------------------------
# Helpers — AST extraction
# ---------------------------------------------------------------------------

_DIAGNOSTICS_PKG = "agent_notes.services.diagnostics"

# Relative depth from _checks.py / _display.py / _fix.py to the package root.
# Each file lives at: agent_notes/services/diagnostics/<file>.py
# One level up  → agent_notes/services/diagnostics   (depth 1)
# Two levels up → agent_notes/services               (depth 2)
# Three levels  → agent_notes                         (depth 3)
# The source files use `from ... import` (level=3) to reach agent_notes.*
_MODULE_ROOT = "agent_notes"


def _anchor_package(filename: str) -> str:
    """Return the dotted package that the source file belongs to.

    _checks.py  →  agent_notes.services.diagnostics
    """
    # All three files live inside agent_notes/services/diagnostics/
    return _DIAGNOSTICS_PKG


def _resolve_relative_import(level: int, module_part: str, anchor: str) -> str:
    """Convert a relative import (level, module_part) to an absolute module path.

    level=1 means 'current package'; level=3 means 'three packages up'.
    anchor is the dotted package path of the file containing the import.
    """
    parts = anchor.split(".")
    # Walk 'level' steps up (level=1 → stay in current package, level=2 → one up, …)
    up_count = level - 1
    base_parts = parts[: len(parts) - up_count] if up_count < len(parts) else parts[:1]
    base = ".".join(base_parts)
    if module_part:
        return f"{base}.{module_part}"
    return base


def _extract_deferred_imports(source_path: Path, anchor: str) -> List[Tuple[str, str]]:
    """Parse *source_path* and return (module_path, repr_for_display) for every
    import that appears inside a function or method body (i.e. deferred imports).

    Returns only the module-level part — not the names imported from it, since
    we only need to verify the module itself is importable.
    """
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    results: List[Tuple[str, str]] = []

    for node in ast.walk(tree):
        # We want imports that are NOT at module level — i.e. they appear inside
        # a FunctionDef / AsyncFunctionDef body.  ast.walk visits everything, so
        # we need to check parent context.  Instead, walk only the bodies of
        # function-like nodes.
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    results.append((alias.name, f"import {alias.name}"))

            elif isinstance(child, ast.ImportFrom):
                if child.module is None:
                    # Bare `from . import something` — the module IS the package
                    module_path = _resolve_relative_import(child.level or 0, "", anchor)
                else:
                    if child.level and child.level > 0:
                        module_path = _resolve_relative_import(
                            child.level, child.module, anchor
                        )
                    else:
                        module_path = child.module
                results.append(
                    (module_path, f"from {'.' * (child.level or 0)}{child.module or ''} import …")
                )

    # Deduplicate while preserving order
    seen: set = set()
    unique = []
    for mod, label in results:
        if mod not in seen:
            seen.add(mod)
            unique.append((mod, label))
    return unique


# ---------------------------------------------------------------------------
# Collect imports from the three diagnostics source files
# ---------------------------------------------------------------------------

_DIAG_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "agent_notes"
    / "services"
    / "diagnostics"
)

_SOURCE_FILES = [
    _DIAG_DIR / "_checks.py",
    _DIAG_DIR / "_display.py",
    _DIAG_DIR / "_fix.py",
]

_ANCHOR = _anchor_package("_checks.py")  # same anchor for all three

_ALL_DEFERRED_IMPORTS: List[Tuple[str, str, str]] = []
for _src_file in _SOURCE_FILES:
    for _mod, _label in _extract_deferred_imports(_src_file, _ANCHOR):
        _ALL_DEFERRED_IMPORTS.append((_mod, _label, _src_file.name))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeferredImportsResolve:
    """Every deferred (function-body) import in the diagnostics subsystem must
    resolve to an importable module without raising ModuleNotFoundError."""

    @pytest.mark.parametrize(
        "module_path,label,source_file",
        _ALL_DEFERRED_IMPORTS,
        ids=[
            f"{src}::{mod}" for mod, _label, src in _ALL_DEFERRED_IMPORTS
        ],
    )
    def test_deferred_import_is_importable(
        self, module_path: str, label: str, source_file: str
    ):
        """Importing *module_path* must not raise ModuleNotFoundError.

        A ModuleNotFoundError here means the function-body import in the
        diagnostics subsystem uses a wrong module path — a bug that would only
        surface at runtime when the function is first called.
        """
        try:
            importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            pytest.fail(
                f"{source_file}: deferred import '{label}' resolves to "
                f"'{module_path}' which cannot be imported.\n"
                f"Original error: {exc}"
            )
        except Exception:
            # Any other exception (ImportError subclass for missing optional
            # dependency, circular import in unrelated code, etc.) is not our
            # concern — we only care that the *module path* itself is valid.
            pass


class TestDiagnosticsPackageImports:
    """The diagnostics __init__.py must be importable and export all documented names."""

    def test_package_is_importable(self):
        """agent_notes.services.diagnostics must import without error."""
        mod = importlib.import_module("agent_notes.services.diagnostics")
        assert mod is not None

    def test_checks_exports_are_present(self):
        """All _checks functions must be present on the diagnostics package."""
        mod = importlib.import_module("agent_notes.services.diagnostics")
        expected = [
            "check_stale_files",
            "check_broken_symlinks",
            "check_shadowed_files",
            "check_missing_files",
            "check_content_drift",
            "check_build_freshness",
        ]
        for name in expected:
            assert hasattr(mod, name), (
                f"agent_notes.services.diagnostics is missing exported name '{name}'"
            )

    def test_display_exports_are_present(self):
        """All _display functions must be present on the diagnostics package."""
        mod = importlib.import_module("agent_notes.services.diagnostics")
        expected = [
            "count_stale",
            "print_summary",
            "print_issues",
            "_count_agents",
            "_count_skills",
            "_count_rules",
            "_check_config",
            "_check_role_models",
        ]
        for name in expected:
            assert hasattr(mod, name), (
                f"agent_notes.services.diagnostics is missing exported name '{name}'"
            )

    def test_fix_export_is_present(self):
        """do_fix must be present on the diagnostics package."""
        mod = importlib.import_module("agent_notes.services.diagnostics")
        assert hasattr(mod, "do_fix"), (
            "agent_notes.services.diagnostics is missing exported name 'do_fix'"
        )

    def test_exported_names_are_callable(self):
        """Every name in __all__ must be callable (a function)."""
        mod = importlib.import_module("agent_notes.services.diagnostics")
        for name in mod.__all__:
            obj = getattr(mod, name, None)
            assert callable(obj), (
                f"agent_notes.services.diagnostics.{name} is not callable (got {type(obj).__name__})"
            )


class TestDeferredImportCount:
    """Guard that the AST extractor actually found deferred imports.

    If the extractor is broken (e.g. returns an empty list), all parametrised
    tests would trivially pass — a false green.  This test ensures we found a
    meaningful set of imports to check.
    """

    def test_at_least_one_deferred_import_was_found(self):
        assert len(_ALL_DEFERRED_IMPORTS) > 0, (
            "AST extractor found zero deferred imports — the extractor itself may be broken"
        )

    def test_deferred_imports_found_across_multiple_files(self):
        source_files = {src for _mod, _label, src in _ALL_DEFERRED_IMPORTS}
        assert len(source_files) >= 2, (
            f"Expected deferred imports from at least 2 source files; "
            f"found only: {source_files}"
        )

    def test_agent_notes_root_modules_are_represented(self):
        """At least one deferred import should be an agent_notes.* absolute path."""
        absolute_an = [
            mod for mod, _label, _src in _ALL_DEFERRED_IMPORTS
            if mod.startswith("agent_notes.")
        ]
        assert len(absolute_an) > 0, (
            "No agent_notes.* absolute module paths found among deferred imports; "
            "relative import resolution may be broken"
        )
