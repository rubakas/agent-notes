"""regenerate places a local install's files inside that install's project,
whatever folder the command runs from (spec 005 Correction 3)."""
from pathlib import Path
from unittest.mock import MagicMock

from agent_notes.commands.regenerate import regenerate
from agent_notes.domain.state import BackendState, ScopeState, State


def test_local_placement_runs_inside_the_project_not_the_cwd(tmp_path, monkeypatch):
    project = (tmp_path / "project").resolve()
    project.mkdir()
    elsewhere = (tmp_path / "elsewhere").resolve()
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    state = State(local_installs={str(project): ScopeState(clis={"claude": BackendState()})})
    monkeypatch.setattr("agent_notes.services.state_store.load_state", lambda: state)
    monkeypatch.setattr("agent_notes.services.state_store.record_install_state", MagicMock())
    monkeypatch.setattr("agent_notes.services.install_state_builder.build_install_state",
                        MagicMock(return_value=State()))
    monkeypatch.setattr("agent_notes.commands.build.generate_agent_files", MagicMock(return_value=[]))
    placed_from = []
    monkeypatch.setattr("agent_notes.services.installer.install_component_for_backend",
                        lambda backend, component, scope, copy: placed_from.append(
                            (component, scope, Path.cwd())))

    regenerate(scope="local", project_path=project)

    assert placed_from, "regenerate placed nothing"
    assert {(component, scope) for component, scope, _ in placed_from} >= {
        ("rules", "local"), ("config", "local"), ("skills", "local")}
    assert {cwd for _, _, cwd in placed_from} == {project}
    assert Path.cwd() == elsewhere


def test_without_a_project_path_local_placement_stays_in_the_cwd(tmp_path, monkeypatch):
    here = (tmp_path / "here").resolve()
    here.mkdir()
    monkeypatch.chdir(here)
    state = State(local_installs={str(here): ScopeState(clis={"claude": BackendState()})})
    monkeypatch.setattr("agent_notes.services.state_store.load_state", lambda: state)
    monkeypatch.setattr("agent_notes.services.state_store.record_install_state", MagicMock())
    monkeypatch.setattr("agent_notes.services.install_state_builder.build_install_state",
                        MagicMock(return_value=State()))
    monkeypatch.setattr("agent_notes.commands.build.generate_agent_files", MagicMock(return_value=[]))
    placed_from = []
    monkeypatch.setattr("agent_notes.services.installer.install_component_for_backend",
                        lambda backend, component, scope, copy: placed_from.append(Path.cwd()))

    regenerate(local=True)

    assert placed_from and set(placed_from) == {here}
