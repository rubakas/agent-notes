"""Config-mode rows (spec 005 FR-015 – FR-018)."""
import pytest

from agent_notes.commands import config_review
from agent_notes.commands.config_review import (
    ConfigContext, InstallRef, config_rows, upgrade_flagged,
)
from agent_notes.commands.wizard.role_models import Catalog
from agent_notes.domain.state import BackendState, ScopeState, State
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.tui.keys import ENTER
from tests.unit.tui.fakes import tui_session, typed


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def _ctx(catalog, tmp_path, *keys, pins=None, efforts=None):
    pins = pins or {"reasoner": "claude-opus-4-6", "worker": "claude-sonnet-5-5",
                    "scout": "claude-gone-1"}
    backend = BackendState(role_models=dict(pins), role_efforts=dict(efforts or {"reasoner": "high"}))
    state = State(local_installs={str(tmp_path): ScopeState(clis={"claude": backend})})
    return ConfigContext(tui_session(*keys), state, InstallRef("local", tmp_path), catalog,
                         load_registry(), {"cost-report": False})


def _rows(ctx):
    return {row.key: row for row in config_rows(ctx)()}


def _model_lines(ctx):
    return {line.split()[0]: line for line in _rows(ctx)["models:claude"].lines()}


def test_rows_in_order(catalog, tmp_path):
    assert list(_rows(_ctx(catalog, tmp_path))) == [
        "models:claude", "memory", "toggle:cost-report", "api-keys", "reinstall"]


def test_a_deprecated_pin_is_flagged_with_the_recommendation(catalog, tmp_path):
    assert "⚠ deprecated  ★ claude-opus-5-5" in _model_lines(_ctx(catalog, tmp_path))["reasoner"]


def test_the_recommended_pin_gets_a_bare_star(catalog, tmp_path):
    assert _model_lines(_ctx(catalog, tmp_path))["worker"].rstrip().endswith("★")


def test_a_current_pin_that_differs_only_hints(catalog, tmp_path):
    line = _model_lines(_ctx(catalog, tmp_path, pins={"worker": "claude-opus-5"}))["worker"]
    assert "★ claude-sonnet-5-5" in line and "⚠" not in line


def test_a_pin_missing_from_the_catalog_is_flagged_not_fatal(catalog, tmp_path):
    assert "⚠ unknown model  ★ claude-haiku-4-5" in _model_lines(_ctx(catalog, tmp_path))["scout"]


def test_u_moves_every_flagged_pin_to_its_star(catalog, tmp_path):
    ctx = _ctx(catalog, tmp_path)
    assert upgrade_flagged(ctx) == 2
    backend = ctx.scope_state().clis["claude"]
    assert backend.role_models == {"reasoner": "claude-opus-5-5", "worker": "claude-sonnet-5-5",
                                   "scout": "claude-haiku-4-5"}
    assert backend.role_efforts == {"reasoner": "high"}


def test_memory_and_cost_report_edit_the_working_copy(catalog, tmp_path, monkeypatch):
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    ctx = _ctx(catalog, tmp_path)
    rows = _rows(ctx)
    rows["memory"].cycle(1)
    rows["toggle:cost-report"].cycle(1)
    assert ctx.state.memory.backend == "obsidian"
    assert ctx.plugins == {"cost-report": True}


def test_api_keys_show_status_only(catalog, tmp_path, monkeypatch):
    from agent_notes.services import credentials
    monkeypatch.setattr(credentials, "list_providers", lambda: ["anthropic"])
    monkeypatch.setattr(credentials, "is_configured", lambda name: name == "anthropic")
    assert _rows(_ctx(catalog, tmp_path))["api-keys"].lines() == ["anthropic ✓ · openai —"]


def test_an_entered_key_is_saved_and_never_shown(catalog, tmp_path, monkeypatch):
    from agent_notes.services import credentials
    saved = []
    monkeypatch.setattr(credentials, "list_providers", lambda: [])
    monkeypatch.setattr(credentials, "is_configured", lambda name: False)
    monkeypatch.setattr(credentials, "set_value", lambda *args: saved.append(args))
    ctx = _ctx(catalog, tmp_path, ENTER, *typed("sk-test-123"), ENTER, ENTER)
    _rows(ctx)["api-keys"].edit()
    assert saved == [("anthropic", "api_key", "sk-test-123")]
    assert all("sk-test-123" not in "\n".join(frame) for frame in ctx.ui.term.frames)


def test_an_empty_key_changes_nothing(catalog, tmp_path, monkeypatch):
    from agent_notes.services import credentials
    saved = []
    monkeypatch.setattr(credentials, "list_providers", lambda: [])
    monkeypatch.setattr(credentials, "is_configured", lambda name: False)
    monkeypatch.setattr(credentials, "set_value", lambda *args: saved.append(args))
    ctx = _ctx(catalog, tmp_path, ENTER, ENTER)
    _rows(ctx)["api-keys"].edit()
    assert saved == []


def test_settings_that_move_files_are_shown_read_only(catalog, tmp_path):
    row = _rows(_ctx(catalog, tmp_path))["reinstall"]
    assert row.focusable is False
    assert "install --reconfigure" in row.lines()[0]


def test_toggles_start_from_the_saved_plugin_config(monkeypatch):
    from agent_notes.registries import plugin_registry
    monkeypatch.setattr("agent_notes.services.user_config.load_user_config", lambda *a, **k: {})
    monkeypatch.setattr(plugin_registry.PluginRegistry, "enabled",
                        lambda self, cfg: [type("P", (), {"name": "cost-report"})()])
    assert config_review.enabled_toggles() == {"cost-report": True}


def test_show_prints_shared_settings_once_then_each_install(catalog, tmp_path, monkeypatch):
    from agent_notes.commands.config_review import render_show
    monkeypatch.setattr(config_review, "enabled_toggles", lambda *a: {"cost-report": False})
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    pins = BackendState(role_models={"reasoner": "claude-opus-4-6"})
    state = State(local_installs={str(a): ScopeState(clis={"claude": pins}),
                                  str(b): ScopeState(clis={"claude": BackendState()})})
    lines = render_show(state, 120)
    text = "\n".join(lines)
    assert text.count("Memory") == 1 and text.count("Cost report") == 1
    assert "built-in" in text
    assert "⚠ deprecated  ★ claude-opus-5-5" in text
    assert "local · " in text and "no pins" in text
    assert not any(line.startswith(" ›") for line in lines) and "↑↓" not in text


def test_show_cuts_a_long_install_label_in_the_middle(tmp_path, monkeypatch):
    from agent_notes.commands.config_review import render_show
    from agent_notes.services.tui.screen import visible_len
    monkeypatch.setattr(config_review, "enabled_toggles", lambda *a: {"cost-report": False})
    project = tmp_path / ("deep" * 10) / "services" / "payments-api"
    project.mkdir(parents=True)
    state = State(local_installs={f"{project}#work": ScopeState(clis={"claude": BackendState()})})
    lines = render_show(state, 60)
    label = next(line for line in lines if line.startswith("local · "))
    assert visible_len(label) <= 60
    assert label.endswith("payments-api · work") and "…" in label
