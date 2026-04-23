"""Test services package structure."""

def test_services_reexports():
    """Test that main services can be imported."""
    from agent_notes.services import fs, ui, state_store, rendering, diff, diagnostics
    assert callable(fs.place_file)
    assert callable(ui.ok)
    assert callable(state_store.load_state)
    assert callable(rendering.generate_agent_files)
    assert callable(diff.diff_states)
    # Note: diagnostics is partially implemented
    assert hasattr(diagnostics, 'check_stale_files')


def test_services_layering():
    """Services may import domain/registries/config, never commands/cli."""
    import ast
    from pathlib import Path
    services_dir = Path(__file__).parent.parent / "agent_notes" / "services"
    for py_file in services_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue  # Skip init files
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            for m in mods:
                if m and m.startswith("agent_notes.commands"):
                    raise AssertionError(f"{py_file.name} imports {m} — services may not depend on commands")
                if m and m.startswith("agent_notes.cli"):
                    raise AssertionError(f"{py_file.name} imports {m} — services may not depend on cli")


def test_backward_compat_shims_still_work():
    """Test that backward compatibility shims work."""
    from agent_notes.install import place_file, remove_symlink
    from agent_notes.config import Color
    from agent_notes.state import load_state, save_state
    from agent_notes.update_diff import diff_states
    # Sanity — all importable
    assert callable(place_file)
    assert Color is not None
    assert callable(load_state)
    assert callable(diff_states)