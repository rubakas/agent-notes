import textwrap
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.registries.agent_registry import load_agent_registry


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def test_skill_available_hides_wip(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    _write(tmp_path / "wipskill" / "SKILL.md", "---\ndescription: x\nstability: wip\n---\n")
    _write(tmp_path / "okskill" / "SKILL.md", "---\ndescription: y\n---\n")
    reg = load_skill_registry(tmp_path)
    assert {s.name for s in reg.available()} == {"okskill"}
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipskill")
    assert {s.name for s in reg.available()} == {"okskill", "wipskill"}


def test_agent_available_hides_wip(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    yaml_path = tmp_path / "agents.yaml"
    _write(yaml_path, """
        agents:
          wipagent: {description: x, role: r, mode: subagent, stability: wip}
          okagent: {description: y, role: r, mode: subagent}
    """)
    reg = load_agent_registry(yaml_path)
    assert {a.name for a in reg.available()} == {"okagent"}
