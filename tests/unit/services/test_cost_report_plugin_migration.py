"""Migration test: cost_report_enabled -> enabled_plugins.cost-report on load."""
from agent_notes.services.user_config import load_user_config


def test_legacy_flag_migrates_to_plugin(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cost_report_enabled: true\n")
    data = load_user_config(cfg)
    assert data["enabled_plugins"]["cost-report"] is True
    assert "cost_report_enabled" not in data


def test_legacy_flag_false_migrates_to_plugin(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cost_report_enabled: false\n")
    data = load_user_config(cfg)
    assert data["enabled_plugins"]["cost-report"] is False
    assert "cost_report_enabled" not in data


def test_legacy_flag_does_not_overwrite_existing_plugin_setting(tmp_path):
    """If enabled_plugins.cost-report is already set, cost_report_enabled is dropped but not applied."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "cost_report_enabled: true\nenabled_plugins:\n  cost-report: false\n"
    )
    data = load_user_config(cfg)
    # setdefault means the existing value (false) wins
    assert data["enabled_plugins"]["cost-report"] is False
    assert "cost_report_enabled" not in data


def test_no_migration_when_legacy_flag_absent(tmp_path):
    """No migration runs when cost_report_enabled is absent."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("agent_roles:\n  coder: haiku\n")
    data = load_user_config(cfg)
    assert "cost_report_enabled" not in data
    assert "enabled_plugins" not in data
