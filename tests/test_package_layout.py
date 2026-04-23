"""Architecture invariant tests for the AgentNotes engine refactor (Phase 13e).

Tests the 4-layer architecture:
1. domain/ — pure dataclasses/types, no imports from other agent_notes packages
2. registries/ — YAML loaders, may import domain+config, not services/commands  
3. services/ — technical concerns, may import domain+registries+config, not commands
4. commands/ — CLI orchestrators, may import everything below

Also tests that top-level shims remain small and circular imports don't occur.
"""

import ast
import importlib
from pathlib import Path


# Get the agent_notes package directory
import agent_notes
PKG_DIR = Path(agent_notes.__file__).parent

# Top-level command modules that registries/services cannot import
FORBIDDEN_TOP_LEVEL_MODULES = {
    "install", "doctor", "wizard", "validate", "update", "build", 
    "list", "memory", "regenerate", "set_role"
}


def _resolve_from_import(py_file: Path, node: ast.ImportFrom) -> list[str]:
    """Resolve an ImportFrom node to a list of fully-qualified module names.

    Handles both absolute (``from a.b import c``) and relative (``from .. import x``)
    imports. For ``from PKG import X``, treats each imported name as PKG.X (so we
    catch ``from .. import install`` pulling in ``agent_notes.install``).
    """
    # Compute the base package that relative imports are anchored to.
    if node.level == 0:
        base = node.module or ""
    else:
        # Walk up ``level`` parents from the file's package.
        rel = py_file.relative_to(PKG_DIR.parent)  # e.g. agent_notes/services/foo.py
        parts = list(rel.parts[:-1])  # drop filename
        if node.level > len(parts):
            return []  # malformed; skip
        base_parts = parts[: len(parts) - (node.level - 1)]
        base = ".".join(base_parts)
        if node.module:
            base = f"{base}.{node.module}"

    results: list[str] = [base] if base else []
    # Also treat each imported name as a potential submodule (``from .. import install``
    # where ``install`` is a module, not just an attribute of the base package).
    for alias in node.names:
        if base:
            results.append(f"{base}.{alias.name}")
    return results


def _collect_imports(py_file: Path) -> list[str]:
    """Return fully-qualified module names referenced by imports in ``py_file``."""
    tree = ast.parse(py_file.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.extend(_resolve_from_import(py_file, node))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
    return names


def _assert_no_forbidden(py_file: Path, forbidden_prefixes: set[str]) -> None:
    """Raise AssertionError if ``py_file`` imports anything starting with a forbidden prefix."""
    for mod in _collect_imports(py_file):
        for prefix in forbidden_prefixes:
            assert not (mod == prefix or mod.startswith(prefix + ".")), (
                f"{py_file.relative_to(PKG_DIR)} imports {mod} — forbidden by layer rules"
            )


def test_domain_has_no_internal_imports():
    """Domain layer must not import from other agent_notes packages (except domain siblings)."""
    domain_dir = PKG_DIR / "domain"
    assert domain_dir.exists(), "agent_notes/domain directory not found"

    for py_file in domain_dir.rglob("*.py"):
        for mod in _collect_imports(py_file):
            if mod.startswith("agent_notes") and not mod.startswith("agent_notes.domain"):
                raise AssertionError(
                    f"{py_file.relative_to(PKG_DIR)} imports {mod} — domain must be pure"
                )


def test_registries_dont_import_services_or_commands():
    """Registries may only import domain+config, not services/commands or top-level modules."""
    registries_dir = PKG_DIR / "registries"
    assert registries_dir.exists(), "agent_notes/registries directory not found"

    forbidden = {"agent_notes.services", "agent_notes.commands"}
    for mod in FORBIDDEN_TOP_LEVEL_MODULES:
        forbidden.add(f"agent_notes.{mod}")

    for py_file in registries_dir.rglob("*.py"):
        _assert_no_forbidden(py_file, forbidden)


def test_services_dont_import_commands():
    """Services may import domain+registries+config, but not commands or top-level modules."""
    services_dir = PKG_DIR / "services"
    assert services_dir.exists(), "agent_notes/services directory not found"

    forbidden = {"agent_notes.commands"}
    for mod in FORBIDDEN_TOP_LEVEL_MODULES:
        forbidden.add(f"agent_notes.{mod}")

    for py_file in services_dir.rglob("*.py"):
        _assert_no_forbidden(py_file, forbidden)


def test_commands_are_thin_orchestrators():
    """Command files should be reasonably sized (thin orchestrators)."""
    commands_dir = PKG_DIR / "commands"
    assert commands_dir.exists(), "agent_notes/commands directory not found"
    
    # Based on task description: wizard.py is ~522 lines, so allow up to 600 as WIP
    max_lines = 600
    
    for py_file in commands_dir.rglob("*.py"):
        if py_file.name == "__pycache__" or py_file.name == "__init__.py":
            continue
            
        line_count = len(py_file.read_text().splitlines())
        assert line_count <= max_lines, \
            f"{py_file.relative_to(PKG_DIR)} has {line_count} lines (max {max_lines}) — commands should be thin orchestrators"


def test_top_level_shims_are_short():
    """Top-level shim files should be small re-export files."""
    shim_files = [
        "install.py", "doctor.py", "wizard.py", "list.py", 
        "validate.py", "update.py", "build.py", "memory.py", 
        "regenerate.py", "set_role.py"
    ]
    
    # Build.py can be up to ~150, others should be much smaller
    max_lines = 150
    
    for shim_name in shim_files:
        shim_file = PKG_DIR / shim_name
        if not shim_file.exists():
            continue  # Skip if file doesn't exist
            
        line_count = len(shim_file.read_text().splitlines())
        assert line_count <= max_lines, \
            f"{shim_name} has {line_count} lines (max {max_lines}) — shims should be short re-export files"


def test_no_circular_imports_at_module_load():
    """Test that agent_notes can be imported without circular import issues."""
    # First test basic import
    try:
        import agent_notes
        # Force reimport to test fresh load
        importlib.reload(agent_notes)
    except Exception as e:
        assert False, f"Failed to import agent_notes: {e}"
    
    # Test that config is properly loaded (sentinel for circular import fix)
    from agent_notes import config
    assert config.DIST_CLAUDE_DIR is not None, \
        "config.DIST_CLAUDE_DIR is None — circular import fallback may have failed"