import textwrap
from agent_notes.registries.cli_registry import load_registry
from agent_notes.registries.plugin_registry import load_plugin_registry


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def _two_backends(tmp_path):
    _write(tmp_path / "wipcli.yaml", """
        name: wipcli
        label: WIP CLI
        global_home: ~/.wipcli
        local_dir: .wipcli
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
        stability: wip
    """)
    _write(tmp_path / "stablecli.yaml", """
        name: stablecli
        label: Stable CLI
        global_home: ~/.stablecli
        local_dir: .stablecli
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
    """)


def test_backend_available_hides_wip_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    _two_backends(tmp_path)
    reg = load_registry(tmp_path)
    names = {b.name for b in reg.available()}
    assert names == {"stablecli"}
    assert {b.name for b in reg.all()} == {"stablecli", "wipcli"}  # all() unchanged


def test_backend_available_shows_wip_when_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipcli")
    _two_backends(tmp_path)
    reg = load_registry(tmp_path)
    assert {b.name for b in reg.available()} == {"stablecli", "wipcli"}


def test_plugin_available_and_enabled_exclude_wip(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    _write(tmp_path / "wipplug" / "plugin.yaml", """
        name: wipplug
        description: WIP plugin
        default: on
        stability: wip
    """)
    reg = load_plugin_registry(tmp_path)
    assert [p.name for p in reg.available()] == []
    # default: on, but wip → not enabled without override
    assert [p.name for p in reg.enabled({})] == []
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipplug")
    assert [p.name for p in reg.enabled({})] == ["wipplug"]
