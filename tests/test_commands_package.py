"""Tests for commands package architecture."""

def test_commands_reexports():
    """Test that all commands are re-exported from the commands package."""
    from agent_notes.commands import (
        install, uninstall, show_info,
        build, doctor, validate, update,
        regenerate, set_role, interactive_install,
    )
    for fn in [install, uninstall, show_info, build, doctor, validate,
               update, regenerate, set_role, interactive_install]:
        assert callable(fn)


def test_commands_do_not_import_other_commands():
    """Each command module is independent — no command imports another command.
    Exception: _install_helpers.py is shared by install/uninstall/info (the install family).
    """
    import ast
    from pathlib import Path
    cmd_dir = Path(__file__).parent.parent / "agent_notes" / "commands"
    for py_file in cmd_dir.rglob("*.py"):
        if py_file.name in ("__init__.py", "_install_helpers.py"):
            continue
        tree = ast.parse(py_file.read_text())
        stem = py_file.stem
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            for m in mods:
                if m.startswith("agent_notes.commands.") and not m.endswith(stem):
                    # Allow the install family to share _install_helpers
                    if m == "agent_notes.commands._install_helpers" and stem in ("install", "uninstall", "info"):
                        continue
                    raise AssertionError(f"{py_file.name} imports {m} — commands must not import other commands")


def test_backward_compat_shims():
    """Every old import path still works."""
    from agent_notes.install import install as I
    from agent_notes.commands.install import install as I2
    assert I is I2
    
    from agent_notes.doctor import doctor as D
    from agent_notes.commands.doctor import doctor as D2
    assert D is D2
    
    from agent_notes.wizard import interactive_install as W
    from agent_notes.commands.wizard import interactive_install as W2
    assert W is W2
    
    from agent_notes.validate import validate as V
    from agent_notes.commands.validate import validate as V2
    assert V is V2