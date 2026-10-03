"""_verify_install counts an installed item present only if it resolves."""
from agent_notes.commands._install_helpers import _verify_install
from agent_notes.domain.state import BackendState, InstalledItem, ScopeState
from agent_notes.registries.cli_registry import load_registry


def _verify(items):
    installed = {"agents": {name: InstalledItem(sha="x", target=str(target), mode="symlink")
                            for name, target in items.items()}}
    scope_state = ScopeState(clis={"claude": BackendState(installed=installed)})
    return _verify_install(scope_state, "global", None, load_registry())


def test_a_dangling_link_is_reported_missing(tmp_path, capsys):
    dangling = tmp_path / "dangling.md"
    dangling.symlink_to(tmp_path / "gone.md")

    issues = _verify({"dangling.md": dangling})

    assert issues == ["Claude Code agents: dangling.md missing"]
    assert "✗ Claude Code agents: 1 missing" in capsys.readouterr().out


def test_a_resolving_link_and_a_regular_file_are_present(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("x")
    link = tmp_path / "link.md"
    link.symlink_to(source)

    assert _verify({"link.md": link, "source.md": source}) == []


def test_a_missing_path_is_reported_missing(tmp_path):
    assert _verify({"nothing.md": tmp_path / "nothing.md"}) == ["Claude Code agents: nothing.md missing"]
