import textwrap
import pytest
from agent_notes.registries.cli_registry import load_registry
from agent_notes.registries.plugin_registry import load_plugin_registry
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.registries.agent_registry import load_agent_registry


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def test_backend_stability_parsed(tmp_path):
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
    reg = load_registry(tmp_path)
    assert reg.get("wipcli").stability == "wip"
    assert reg.get("stablecli").stability == "stable"  # absent → stable


def test_backend_invalid_stability_rejected(tmp_path):
    _write(tmp_path / "bad.yaml", """
        name: bad
        label: Bad
        global_home: ~/.bad
        local_dir: .bad
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
        stability: beta
    """)
    with pytest.raises(ValueError):
        load_registry(tmp_path)


def test_plugin_stability_parsed(tmp_path):
    _write(tmp_path / "wipplug" / "plugin.yaml", """
        name: wipplug
        description: WIP plugin
        default: off
        stability: wip
    """)
    reg = load_plugin_registry(tmp_path)
    assert reg.get("wipplug").stability == "wip"


def test_skill_stability_parsed(tmp_path):
    _write(tmp_path / "wipskill" / "SKILL.md", """\
        ---
        description: "A WIP skill"
        stability: wip
        ---
        body
    """)
    reg = load_skill_registry(tmp_path)
    assert reg.get("wipskill").stability == "wip"


def test_agent_stability_parsed(tmp_path):
    yaml_path = tmp_path / "agents.yaml"
    _write(yaml_path, """
        agents:
          wipagent:
            description: WIP agent
            role: helper
            mode: subagent
            stability: wip
          stableagent:
            description: Stable agent
            role: helper
            mode: subagent
    """)
    reg = load_agent_registry(yaml_path)
    assert reg.get("wipagent").stability == "wip"
    assert reg.get("stableagent").stability == "stable"
    # stability must NOT be treated as a per-backend override
    assert "stability" not in reg.get("wipagent").backends


def test_memory_backend_default_stability():
    from agent_notes.memory.memory_backend import get_backend
    assert get_backend("local").stability == "stable"
    assert get_backend("obsidian").stability == "stable"
