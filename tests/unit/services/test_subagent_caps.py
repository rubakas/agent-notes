"""The Claude subagent caps (env.CLAUDE_CODE_MAX_*) agent-notes merges into settings.json:
written only when absent, recorded in install state, removed only while still at our value."""
import json
from pathlib import Path

import pytest

from agent_notes.constants import SubagentCaps
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services import settings_writer as sw
from agent_notes.services.install_ownership import replacing
from agent_notes.services.install_state_builder import build_install_state
from agent_notes.services.installer import _install_session_hook, _uninstall_session_hook
from agent_notes.services.state_store import (
    get_scope, load_state, save_state, _backend_from_dict, _backend_to_dict,
)
from agent_notes.domain.state import BackendState

DEPTH = "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"
CONCURRENT = "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"
OURS = {DEPTH: "1", CONCURRENT: "5"}


@pytest.fixture
def claude_home(tmp_path):
    home = tmp_path / "claude-home"
    home.mkdir()
    return home


@pytest.fixture
def backend(claude_home):
    return load_registry().get("claude").with_global_home(claude_home)


def _settings(claude_home) -> dict:
    return json.loads((claude_home / "settings.json").read_text())


def _put(claude_home, data) -> None:
    (claude_home / "settings.json").write_text(json.dumps(data))


def _install(backend, claude_home) -> dict:
    """One install run: the session hook, then the manifest, saved. Returns the recorded env."""
    prior = load_state()
    with replacing(get_scope(prior, "global") if prior else None):
        _install_session_hook(backend, "global")
    state = build_install_state(mode="copy", scope="global", repo_root=Path.cwd(),
                                selected_clis={"claude"}, global_home_override=str(claude_home))
    save_state(state)
    return state.global_install.clis["claude"].settings_env


def _uninstall(backend) -> None:
    state = load_state()
    with replacing(get_scope(state, "global") if state else None):
        _uninstall_session_hook(backend, "global")


class TestInstallEnvEntries:
    def test_writes_absent_keys_and_reports_them(self, tmp_path):
        path = tmp_path / "settings.json"

        assert sorted(sw.install_env_entries(path, OURS)) == sorted(OURS)
        assert json.loads(path.read_text())["env"] == OURS

    def test_keeps_user_values_and_other_env(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"env": {DEPTH: "3", "FOO": "bar"}}))

        assert sw.install_env_entries(path, OURS) == [CONCURRENT]
        assert json.loads(path.read_text())["env"] == {DEPTH: "3", "FOO": "bar", CONCURRENT: "5"}

    def test_all_present_leaves_file_untouched(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"env": {DEPTH: "3", CONCURRENT: "9"}}))
        before = path.read_bytes()

        assert sw.install_env_entries(path, OURS) == []
        assert path.read_bytes() == before

    @pytest.mark.parametrize("env", ["text", ["a"], 7, None])
    def test_malformed_env_is_left_alone(self, tmp_path, env):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"env": env, "model": "x"}))
        before = path.read_bytes()

        assert sw.install_env_entries(path, OURS) == []
        assert path.read_bytes() == before

    def test_unparseable_file_is_left_alone(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{ not json")

        assert sw.install_env_entries(path, OURS) == []
        assert path.read_text() == "{ not json"


class TestRemoveEnvEntries:
    def test_removes_only_keys_still_at_our_value(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"env": {DEPTH: "1", CONCURRENT: "8", "FOO": "bar"}}))

        sw.remove_env_entries(path, OURS)

        assert json.loads(path.read_text())["env"] == {CONCURRENT: "8", "FOO": "bar"}

    def test_emptied_env_goes(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"env": dict(OURS), "model": "x"}))

        sw.remove_env_entries(path, OURS)

        assert json.loads(path.read_text()) == {"model": "x"}

    @pytest.mark.parametrize("data", [{}, {"env": "text"}, {"env": ["a"]}, {"env": None}])
    def test_absent_or_malformed_env_does_not_raise(self, tmp_path, data):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps(data))
        before = path.read_bytes()

        sw.remove_env_entries(path, OURS)

        assert path.read_bytes() == before

    def test_missing_file_does_not_raise(self, tmp_path):
        sw.remove_env_entries(tmp_path / "settings.json", OURS)

        assert not (tmp_path / "settings.json").exists()


class TestInstallAndUninstall:
    def test_fresh_install_writes_both_keys_and_records_them(self, backend, claude_home):
        recorded = _install(backend, claude_home)

        assert _settings(claude_home)["env"] == OURS
        assert recorded == OURS

    def test_existing_user_value_is_kept_and_not_recorded(self, backend, claude_home):
        _put(claude_home, {"env": {DEPTH: "3"}})

        recorded = _install(backend, claude_home)

        assert _settings(claude_home)["env"] == {DEPTH: "3", CONCURRENT: "5"}
        assert recorded == {CONCURRENT: "5"}

    def test_a_user_value_equal_to_ours_is_not_claimed(self, backend, claude_home):
        _put(claude_home, {"env": {DEPTH: "1"}})

        recorded = _install(backend, claude_home)

        assert recorded == {CONCURRENT: "5"}
        _uninstall(backend)
        assert _settings(claude_home)["env"] == {DEPTH: "1"}

    def test_uninstall_removes_ours_and_keeps_a_changed_value(self, backend, claude_home):
        _install(backend, claude_home)
        settings = _settings(claude_home)
        settings["env"][CONCURRENT] = "9"
        settings["env"]["FOO"] = "bar"
        _put(claude_home, settings)

        _uninstall(backend)

        assert _settings(claude_home)["env"] == {CONCURRENT: "9", "FOO": "bar"}

    def test_uninstall_leaves_no_env_behind_when_untouched(self, backend, claude_home):
        _install(backend, claude_home)
        _put(claude_home, {**_settings(claude_home), "model": "x"})

        _uninstall(backend)

        assert "env" not in _settings(claude_home)

    def test_uninstall_without_a_record_touches_nothing(self, backend, claude_home):
        _put(claude_home, {"env": dict(OURS)})   # the user set these themselves

        _uninstall(backend)

        assert _settings(claude_home)["env"] == OURS

    def test_reinstall_is_idempotent(self, backend, claude_home):
        first = _install(backend, claude_home)
        after_first = (claude_home / "settings.json").read_bytes()

        second = _install(backend, claude_home)

        assert first == second == OURS
        assert (claude_home / "settings.json").read_bytes() == after_first
        assert list(load_state().global_install.clis["claude"].settings_env) == list(OURS)

    def test_reinstall_keeps_a_user_value_unclaimed(self, backend, claude_home):
        _put(claude_home, {"env": {DEPTH: "3"}})
        _install(backend, claude_home)

        assert _install(backend, claude_home) == {CONCURRENT: "5"}
        assert _settings(claude_home)["env"][DEPTH] == "3"

    def test_malformed_env_survives_install_and_uninstall(self, backend, claude_home):
        _put(claude_home, {"env": "oops"})

        assert _install(backend, claude_home) == {}
        _uninstall(backend)

        assert _settings(claude_home)["env"] == "oops"

    def test_other_cli_gets_no_caps(self, claude_home):
        codex = load_registry().get("codex")

        assert not codex.supports("subagent_caps")
        assert load_registry().get("claude").supports("subagent_caps")


class TestStateRoundTrip:
    def test_settings_env_round_trips(self):
        original = BackendState(settings_env=dict(OURS))

        assert _backend_from_dict(_backend_to_dict(original)).settings_env == OURS

    def test_empty_record_is_not_serialised(self):
        assert "settings_env" not in _backend_to_dict(BackendState())

    def test_state_without_the_field_loads_empty(self):
        assert _backend_from_dict({"installed": {}}).settings_env == {}

    def test_malformed_field_is_dropped(self):
        assert _backend_from_dict({"settings_env": {DEPTH: 1, CONCURRENT: "5"}}).settings_env == {CONCURRENT: "5"}
