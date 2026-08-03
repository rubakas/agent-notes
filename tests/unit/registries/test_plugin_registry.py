from pathlib import Path
import textwrap
from agent_notes.registries.plugin_registry import load_plugin_registry


def _write_manifest(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text(textwrap.dedent(body))


def test_loads_manifest_fields(tmp_path):
    _write_manifest(tmp_path, "cost-report", """
        name: cost-report
        description: Per-session token cost reporting
        default: off
        includes: [cost_reporting]
        hooks:
          - {event: Stop, command: "agent-notes cost-report", requires: stop_hook}
        allow:
          - {value: "Bash(agent-notes cost-report)", requires: allow_entries}
    """)
    reg = load_plugin_registry(tmp_path)
    p = reg.get("cost-report")
    assert p.default is False
    assert p.includes == ("cost_reporting",)
    assert p.hooks[0].event == "Stop"
    assert p.hooks[0].command == "agent-notes cost-report"
    assert p.hooks[0].requires == "stop_hook"
    assert p.allow[0].value == "Bash(agent-notes cost-report)"


def test_enabled_uses_default_then_override(tmp_path):
    _write_manifest(tmp_path, "on-plugin", "name: on-plugin\ndescription: x\ndefault: on\n")
    _write_manifest(tmp_path, "off-plugin", "name: off-plugin\ndescription: y\ndefault: off\n")
    reg = load_plugin_registry(tmp_path)
    assert {p.name for p in reg.enabled({})} == {"on-plugin"}
    assert {p.name for p in reg.enabled({"enabled_plugins": {"off-plugin": True, "on-plugin": False}})} == {"off-plugin"}


def test_rejects_name_directory_mismatch(tmp_path):
    _write_manifest(tmp_path, "dirname", "name: other\ndescription: x\ndefault: on\n")
    try:
        load_plugin_registry(tmp_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "dirname" in str(e)


def test_missing_required_field_raises(tmp_path):
    _write_manifest(tmp_path, "bad", "name: bad\ndefault: on\n")  # no description
    try:
        load_plugin_registry(tmp_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "description" in str(e)
