"""Tests for agent_notes.services.user_config."""
import pytest
from pathlib import Path

from agent_notes.services.user_config import (
    load_user_config,
    resolve_agent_role,
    resolve_role_model,
    get_patch,
    merge_configs,
)


def test_load_user_config_missing_file(tmp_path):
    result = load_user_config(tmp_path / "nonexistent.yaml")
    assert result == {}


def test_load_user_config_valid_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("agent_roles:\n  coder: heavy\n")
    result = load_user_config(config_file)
    assert result == {"agent_roles": {"coder": "heavy"}}


def test_load_user_config_empty_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    result = load_user_config(config_file)
    assert result == {}


def test_load_user_config_corrupt_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("key: [unclosed")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_user_config(config_file)


def test_resolve_agent_role_no_override():
    config = {}
    result = resolve_agent_role("coder", "default-role", config)
    assert result == "default-role"


def test_resolve_agent_role_with_override():
    config = {"agent_roles": {"coder": "heavy"}}
    result = resolve_agent_role("coder", "default-role", config)
    assert result == "heavy"


def test_resolve_agent_role_other_agent_not_overridden():
    config = {"agent_roles": {"coder": "heavy"}}
    result = resolve_agent_role("reviewer", "light", config)
    assert result == "light"


def test_resolve_role_model_no_override():
    config = {}
    result = resolve_role_model("heavy", "claude", config)
    assert result is None


def test_resolve_role_model_with_override():
    config = {"role_models": {"claude": {"heavy": "claude-opus-4-7"}}}
    result = resolve_role_model("heavy", "claude", config)
    assert result == "claude-opus-4-7"


def test_resolve_role_model_backend_not_present():
    config = {"role_models": {"opencode": {"heavy": "gpt-4o"}}}
    result = resolve_role_model("heavy", "claude", config)
    assert result is None


def test_resolve_role_model_role_not_present():
    config = {"role_models": {"claude": {"light": "haiku"}}}
    result = resolve_role_model("heavy", "claude", config)
    assert result is None


def test_get_patch_no_patch():
    config = {}
    result = get_patch("coder", config)
    assert result is None


def test_get_patch_with_patch():
    config = {"patches": {"coder": "Always write tests."}}
    result = get_patch("coder", config)
    assert result == "Always write tests."


def test_get_patch_other_agent_not_patched():
    config = {"patches": {"coder": "Always write tests."}}
    result = get_patch("reviewer", config)
    assert result is None


def test_merge_configs_basic():
    base = {"agent_roles": {"coder": "heavy"}}
    override = {"agent_roles": {"reviewer": "light"}}
    result = merge_configs(base, override)
    assert result == {"agent_roles": {"coder": "heavy", "reviewer": "light"}}


def test_merge_configs_override_wins():
    base = {"agent_roles": {"coder": "heavy"}}
    override = {"agent_roles": {"coder": "light"}}
    result = merge_configs(base, override)
    assert result == {"agent_roles": {"coder": "light"}}


def test_merge_configs_new_top_level_key():
    base = {"agent_roles": {"coder": "heavy"}}
    override = {"role_models": {"claude": {"heavy": "opus"}}}
    result = merge_configs(base, override)
    assert result["agent_roles"] == {"coder": "heavy"}
    assert result["role_models"] == {"claude": {"heavy": "opus"}}


def test_merge_configs_patch_concatenation():
    base = {"patches": {"coder": "First patch."}}
    override = {"patches": {"coder": "Second patch."}}
    result = merge_configs(base, override)
    assert result["patches"]["coder"] == "First patch.\n\nSecond patch."


def test_merge_configs_patch_new_agent():
    base = {"patches": {"coder": "First patch."}}
    override = {"patches": {"reviewer": "Reviewer patch."}}
    result = merge_configs(base, override)
    assert result["patches"]["coder"] == "First patch."
    assert result["patches"]["reviewer"] == "Reviewer patch."


def test_merge_configs_does_not_mutate_base():
    base = {"agent_roles": {"coder": "heavy"}}
    override = {"agent_roles": {"coder": "light"}}
    merge_configs(base, override)
    assert base["agent_roles"]["coder"] == "heavy"
