"""Load-time validation of declared effort values.

Roles and agents are provider-agnostic, so their effort must name a value some
provider understands. An unrecognized value (a typo) would otherwise render as
the provider's default and never be noticed, so it fails at load instead.
"""

from __future__ import annotations

import pytest

from agent_notes.registries.agent_registry import load_agent_registry
from agent_notes.registries.provider_registry import known_efforts, validate_effort
from agent_notes.registries.role_registry import load_role_registry


ROLE_YAML = """\
name: worker
label: Worker
description: Does the work
{effort_line}
"""

AGENTS_YAML = """\
agents:
  coder:
    description: Writes code
    role: worker
    mode: subagent
{effort_line}
"""


def _write_role(tmp_path, effort_line):
    roles_dir = tmp_path / "roles"
    roles_dir.mkdir()
    (roles_dir / "worker.yaml").write_text(ROLE_YAML.format(effort_line=effort_line))
    return roles_dir


def _write_agents(tmp_path, effort_line):
    path = tmp_path / "agents.yaml"
    path.write_text(AGENTS_YAML.format(effort_line=effort_line))
    return path


class TestKnownEfforts:
    def test_union_spans_every_provider_vocabulary(self):
        efforts = known_efforts()
        assert {"low", "medium", "high", "xhigh"} <= efforts
        assert "max" in efforts
        assert "minimal" in efforts   # openai-only
        assert "none" in efforts      # openai-only

    def test_empty_value_is_legal(self):
        assert validate_effort("", "somewhere") == ""
        assert validate_effort(None, "somewhere") == ""


class TestRoleEffortValidation:
    def test_typo_is_rejected_at_load(self, tmp_path):
        roles_dir = _write_role(tmp_path, "typical_effort: hgih")
        with pytest.raises(ValueError, match="Unknown effort 'hgih'"):
            load_role_registry(roles_dir)

    def test_known_value_loads(self, tmp_path):
        roles_dir = _write_role(tmp_path, "typical_effort: max")
        assert load_role_registry(roles_dir).get("worker").typical_effort == "max"

    def test_absent_value_loads_as_unset(self, tmp_path):
        roles_dir = _write_role(tmp_path, "")
        assert load_role_registry(roles_dir).get("worker").typical_effort == ""


class TestAgentEffortValidation:
    def test_typo_is_rejected_at_load(self, tmp_path):
        path = _write_agents(tmp_path, "    effort: hgih")
        with pytest.raises(ValueError, match="Unknown effort 'hgih'"):
            load_agent_registry(path)

    def test_known_value_loads(self, tmp_path):
        path = _write_agents(tmp_path, "    effort: minimal")
        assert load_agent_registry(path).get("coder").effort == "minimal"

    def test_absent_value_loads_as_none(self, tmp_path):
        path = _write_agents(tmp_path, "")
        assert load_agent_registry(path).get("coder").effort is None


class TestBuildLoaderValidation:
    """build reads agents.yaml directly (not through the registry), so the same
    check has to hold on that path."""

    def test_typo_is_rejected_by_load_agents_config(self, tmp_path, monkeypatch):
        from agent_notes.services.rendering import load_agents_config

        path = _write_agents(tmp_path, "    effort: hgih")
        monkeypatch.setattr("agent_notes.config.AGENTS_YAML", path)
        with pytest.raises(ValueError, match="Unknown effort 'hgih'"):
            load_agents_config()


class TestShippedDataIsValid:
    def test_every_shipped_role_and_agent_effort_is_known(self):
        load_role_registry()
        load_agent_registry()
