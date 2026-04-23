def test_domain_reexports():
    from agent_notes.domain import (
        CLIBackend, Model, Role, State, ScopeState,
        BackendState, InstalledItem, Issue, FixAction,
        ValidationError, ValidationWarning, ComponentDiff, StateDiff,
    )
    for cls in [CLIBackend, Model, Role, State, ScopeState, BackendState,
                InstalledItem, Issue, FixAction, ValidationError,
                ValidationWarning, ComponentDiff, StateDiff]:
        assert isinstance(cls, type)


def test_backward_compat_imports_still_work():
    from agent_notes.cli_backend import CLIBackend as CB1
    from agent_notes.domain import CLIBackend as CB2
    assert CB1 is CB2
    from agent_notes.state import State as S1
    from agent_notes.domain import State as S2
    assert S1 is S2
    from agent_notes.model_registry import Model as M1
    from agent_notes.domain import Model as M2
    assert M1 is M2
    from agent_notes.role_registry import Role as R1
    from agent_notes.domain import Role as R2
    assert R1 is R2
    from agent_notes.doctor import Issue as I1
    from agent_notes.domain import Issue as I2
    assert I1 is I2
    from agent_notes.validate import ValidationError as V1
    from agent_notes.domain import ValidationError as V2
    assert V1 is V2
    from agent_notes.update_diff import StateDiff as D1
    from agent_notes.domain import StateDiff as D2
    assert D1 is D2


def test_domain_has_no_agent_notes_deps():
    """Enforce the key invariant: domain must not import anything from agent_notes."""
    from pathlib import Path
    import ast
    domain_dir = Path(__file__).parent.parent / "agent_notes" / "domain"
    for py_file in domain_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("agent_notes") or mod.startswith("agent_notes.domain"), \
                    f"{py_file.name} imports from {mod} — domain must be pure"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("agent_notes.") or \
                           alias.name.startswith("agent_notes.domain"), \
                           f"{py_file.name} imports {alias.name} — domain must be pure"