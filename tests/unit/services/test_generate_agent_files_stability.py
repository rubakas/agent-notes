"""Regression test: the agent build gate must normalize `stability` the same
way every other component family does (registry load time).

The bug: generate_agent_files() compared the RAW `agents.yaml` value
(`c.get("stability", "stable")`) against STABILITY_WIP, so a non-canonical
value like "WIP" (uppercase) or " wip " never equalled "wip" and the agent
leaked into the build despite being intended as work-in-progress.
"""
import copy
from pathlib import Path
from unittest.mock import patch

import agent_notes.config as config_mod
from agent_notes.services.rendering import generate_agent_files, load_agents_config


def _agents_subset_with_stability(name, stability):
    agents_config = load_agents_config()
    cfg = copy.deepcopy(agents_config[name])
    cfg["stability"] = stability
    return {name: cfg}


def _render(tmp_path, monkeypatch, agents_config, **kwargs):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    dist = tmp_path / "dist"
    with patch.object(config_mod, "DIST_DIR", dist), \
         patch("agent_notes.services.user_config.load_user_config", return_value={}):
        generate_agent_files(agents_config, **kwargs)
    return dist


class TestBuildGateNormalizesStability:
    def test_noncanonical_wip_agent_excluded_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
        agents_config = _agents_subset_with_stability("coder", "WIP")

        dist = _render(tmp_path, monkeypatch, agents_config)

        assert not (dist / "claude" / "agents" / "coder.md").exists()

    def test_noncanonical_wip_agent_included_with_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "coder")
        agents_config = _agents_subset_with_stability("coder", "WIP")

        dist = _render(tmp_path, monkeypatch, agents_config)

        assert (dist / "claude" / "agents" / "coder.md").exists()
