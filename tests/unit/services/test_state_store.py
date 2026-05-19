"""Tests for agent_notes.services.state_store."""
import json
import pytest
from pathlib import Path

from agent_notes.services.state_store import (
    load_state,
    save_state,
    clear_state,
    get_scope,
    set_scope,
    remove_scope,
    default_state,
    now_iso,
    sha256_of,
    remove_install_state,
    load_current_state,
    record_install_state,
    state_dir,
    state_file,
    _state_to_dict,
    _state_from_dict,
)
from agent_notes.domain.state import (
    State,
    ScopeState,
    BackendState,
    InstalledItem,
    MemoryConfig,
    MigrationState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(installed_at: str = "2026-01-01T00:00:00Z", mode: str = "symlink") -> ScopeState:
    return ScopeState(
        installed_at=installed_at,
        updated_at=installed_at,
        mode=mode,
        installed_version="2.0.0",
    )


def _make_state_with_global() -> State:
    return State(
        source_path="/fake/path",
        source_commit="abc123",
        global_install=_make_scope(),
        local_installs={},
    )


# ---------------------------------------------------------------------------
# TestStateDir
# ---------------------------------------------------------------------------

class TestStateDir:
    def test_returns_path_ending_in_agent_notes(self):
        result = state_dir()
        assert result.name == "agent-notes"

    def test_respects_xdg_config_home(self, monkeypatch, tmp_path):
        custom_config = tmp_path / "custom-config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_config))
        result = state_dir()
        assert result == custom_config / "agent-notes"

    def test_uses_home_dot_config_when_no_xdg(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = state_dir()
        assert str(result).endswith("/.config/agent-notes")

    def test_state_file_is_json(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = state_file()
        assert result.suffix == ".json"
        assert result.name == "state.json"


# ---------------------------------------------------------------------------
# TestDefaultState
# ---------------------------------------------------------------------------

class TestDefaultState:
    def test_returns_state_instance(self):
        s = default_state()
        assert isinstance(s, State)

    def test_global_install_is_none(self):
        s = default_state()
        assert s.global_install is None

    def test_local_installs_is_empty_dict(self):
        s = default_state()
        assert s.local_installs == {}

    def test_source_path_is_empty_string(self):
        s = default_state()
        assert s.source_path == ""

    def test_source_commit_is_empty_string(self):
        s = default_state()
        assert s.source_commit == ""


# ---------------------------------------------------------------------------
# TestLoadState
# ---------------------------------------------------------------------------

class TestLoadState:
    def test_returns_none_when_file_absent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        assert load_state() is None

    def test_returns_none_on_corrupted_json(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config" / "agent-notes"
        config_dir.mkdir(parents=True)
        (config_dir / "state.json").write_text("{ not valid json {{")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        assert load_state() is None

    def test_returns_none_on_empty_file(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config" / "agent-notes"
        config_dir.mkdir(parents=True)
        (config_dir / "state.json").write_text("")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        assert load_state() is None

    def test_returns_state_when_file_valid(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config" / "agent-notes"
        config_dir.mkdir(parents=True)
        data = {
            "source_path": "/src",
            "source_commit": "abc",
            "global": None,
            "local": {},
            "memory": {"backend": "local", "path": ""},
        }
        (config_dir / "state.json").write_text(json.dumps(data))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        result = load_state()
        assert isinstance(result, State)

    def test_loaded_state_has_correct_source_path(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config" / "agent-notes"
        config_dir.mkdir(parents=True)
        data = {
            "source_path": "/my/src",
            "source_commit": "deadbeef",
            "global": None,
            "local": {},
            "memory": {"backend": "local", "path": ""},
        }
        (config_dir / "state.json").write_text(json.dumps(data))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        result = load_state()
        assert result.source_path == "/my/src"

    def test_loaded_state_global_install_is_none_when_null_in_json(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config" / "agent-notes"
        config_dir.mkdir(parents=True)
        data = {"source_path": "", "source_commit": "", "global": None, "local": {}}
        (config_dir / "state.json").write_text(json.dumps(data))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        result = load_state()
        assert result.global_install is None

    def test_loaded_state_restores_global_scope(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config" / "agent-notes"
        config_dir.mkdir(parents=True)
        data = {
            "source_path": "",
            "source_commit": "",
            "global": {
                "installed_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "mode": "copy",
                "installed_version": "1.5.0",
                "clis": {},
            },
            "local": {},
        }
        (config_dir / "state.json").write_text(json.dumps(data))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        result = load_state()
        assert result.global_install is not None
        assert result.global_install.mode == "copy"
        assert result.global_install.installed_version == "1.5.0"


# ---------------------------------------------------------------------------
# TestSaveState
# ---------------------------------------------------------------------------

class TestSaveState:
    def test_creates_state_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = default_state()
        save_state(state)
        assert state_file().exists()

    def test_saved_state_is_valid_json(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = default_state()
        save_state(state)
        content = state_file().read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_saved_state_contains_source_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = State(source_path="/my/src", source_commit="xyz", global_install=None, local_installs={})
        save_state(state)
        data = json.loads(state_file().read_text())
        assert data["source_path"] == "/my/src"

    def test_save_creates_parent_directories(self, monkeypatch, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(deep))
        state = default_state()
        save_state(state)
        assert state_file().exists()

    def test_roundtrip_global_install(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = _make_state_with_global()
        save_state(state)
        loaded = load_state()
        assert loaded is not None
        assert loaded.global_install is not None
        assert loaded.global_install.mode == "symlink"

    def test_roundtrip_local_installs(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={
                "/home/user/proj": _make_scope(mode="copy"),
            },
        )
        save_state(state)
        loaded = load_state()
        assert "/home/user/proj" in loaded.local_installs
        assert loaded.local_installs["/home/user/proj"].mode == "copy"

    def test_save_updates_updated_at_for_global(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = _make_state_with_global()
        old_updated_at = state.global_install.updated_at
        import time; time.sleep(1.1)
        save_state(state)
        loaded = load_state()
        # updated_at should have been refreshed
        assert loaded.global_install.updated_at >= old_updated_at

    def test_save_does_not_leave_tmp_file_on_success(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = default_state()
        save_state(state)
        tmp_file = state_file().with_suffix(".json.tmp")
        assert not tmp_file.exists()


# ---------------------------------------------------------------------------
# TestClearState
# ---------------------------------------------------------------------------

class TestClearState:
    def test_removes_state_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = default_state()
        save_state(state)
        assert state_file().exists()
        clear_state()
        assert not state_file().exists()

    def test_no_error_when_file_absent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        # File doesn't exist — should not raise
        clear_state()


# ---------------------------------------------------------------------------
# TestGetScope
# ---------------------------------------------------------------------------

class TestGetScope:
    def test_get_global_scope_returns_global_install(self):
        scope = _make_scope()
        state = State(source_path="", source_commit="", global_install=scope, local_installs={})
        result = get_scope(state, "global")
        assert result is scope

    def test_get_global_scope_returns_none_when_not_set(self):
        state = default_state()
        result = get_scope(state, "global")
        assert result is None

    def test_get_local_scope_returns_correct_scope(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        scope = _make_scope()
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={str(project.resolve()): scope},
        )
        result = get_scope(state, "local", project_path=project)
        assert result is scope

    def test_get_local_scope_requires_project_path(self):
        state = default_state()
        with pytest.raises(ValueError, match="project_path"):
            get_scope(state, "local")

    def test_get_local_scope_returns_none_for_unknown_project(self, tmp_path):
        state = default_state()
        result = get_scope(state, "local", project_path=tmp_path / "unknown")
        assert result is None

    def test_unknown_scope_raises_value_error(self):
        state = default_state()
        with pytest.raises(ValueError, match="Unknown scope"):
            get_scope(state, "staging")


# ---------------------------------------------------------------------------
# TestSetScope
# ---------------------------------------------------------------------------

class TestSetScope:
    def test_set_global_scope(self):
        state = default_state()
        scope = _make_scope()
        set_scope(state, "global", scope)
        assert state.global_install is scope

    def test_set_local_scope(self, tmp_path):
        state = default_state()
        project = tmp_path / "proj"
        scope = _make_scope()
        set_scope(state, "local", scope, project_path=project)
        assert str(project.resolve()) in state.local_installs

    def test_set_local_scope_requires_project_path(self):
        state = default_state()
        with pytest.raises(ValueError, match="project_path"):
            set_scope(state, "local", _make_scope())

    def test_set_unknown_scope_raises_value_error(self):
        state = default_state()
        with pytest.raises(ValueError, match="Unknown scope"):
            set_scope(state, "staging", _make_scope())

    def test_set_global_scope_overwrites_existing(self):
        state = default_state()
        scope_a = _make_scope(mode="symlink")
        scope_b = _make_scope(mode="copy")
        set_scope(state, "global", scope_a)
        set_scope(state, "global", scope_b)
        assert state.global_install.mode == "copy"


# ---------------------------------------------------------------------------
# TestRemoveScope
# ---------------------------------------------------------------------------

class TestRemoveScope:
    def test_remove_global_sets_to_none(self):
        state = _make_state_with_global()
        remove_scope(state, "global")
        assert state.global_install is None

    def test_remove_local_scope(self, tmp_path):
        project = tmp_path / "proj"
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={str(project.resolve()): _make_scope()},
        )
        remove_scope(state, "local", project_path=project)
        assert str(project.resolve()) not in state.local_installs

    def test_remove_local_scope_requires_project_path(self):
        state = default_state()
        with pytest.raises(ValueError, match="project_path"):
            remove_scope(state, "local")

    def test_remove_local_scope_noop_when_not_present(self, tmp_path):
        state = default_state()
        # Should not raise even when project not in state
        remove_scope(state, "local", project_path=tmp_path / "nonexistent")
        assert state.local_installs == {}


# ---------------------------------------------------------------------------
# TestRemoveInstallState
# ---------------------------------------------------------------------------

class TestRemoveInstallState:
    def test_noop_when_no_state_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        # Should not raise
        remove_install_state("global")

    def test_removes_global_scope_leaves_local(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        project = "/home/user/myproj"
        state = State(
            source_path="",
            source_commit="",
            global_install=_make_scope(),
            local_installs={project: _make_scope()},
        )
        save_state(state)
        remove_install_state("global")
        loaded = load_state()
        assert loaded is not None
        assert loaded.global_install is None
        assert project in loaded.local_installs

    def test_removes_local_scope_leaves_global(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        project = tmp_path / "proj"
        state = State(
            source_path="",
            source_commit="",
            global_install=_make_scope(),
            local_installs={str(project.resolve()): _make_scope()},
        )
        save_state(state)
        remove_install_state("local", project_path=project)
        loaded = load_state()
        assert loaded is not None
        assert loaded.global_install is not None
        assert str(project.resolve()) not in loaded.local_installs

    def test_clears_state_file_when_all_scopes_removed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = State(
            source_path="",
            source_commit="",
            global_install=_make_scope(),
            local_installs={},
        )
        save_state(state)
        remove_install_state("global")
        # State file should be deleted when nothing remains
        assert not state_file().exists()


# ---------------------------------------------------------------------------
# TestNowIso
# ---------------------------------------------------------------------------

class TestNowIso:
    def test_returns_string(self):
        assert isinstance(now_iso(), str)

    def test_ends_with_z(self):
        assert now_iso().endswith("Z")

    def test_matches_iso_8601_format(self):
        import re
        result = now_iso()
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result)

    def test_two_calls_produce_close_values(self):
        t1 = now_iso()
        t2 = now_iso()
        # Same second or consecutive — lexicographic comparison works for ISO timestamps
        assert t2 >= t1


# ---------------------------------------------------------------------------
# TestSha256Of
# ---------------------------------------------------------------------------

class TestSha256Of:
    def test_returns_hex_string(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_bytes(b"hello")
        result = sha256_of(f)
        assert isinstance(result, str)
        assert len(result) == 64  # sha256 hex digest length

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"same content")
        f2.write_bytes(b"same content")
        assert sha256_of(f1) == sha256_of(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello")
        f2.write_bytes(b"world")
        assert sha256_of(f1) != sha256_of(f2)


# ---------------------------------------------------------------------------
# TestStateSerializationRoundtrip
# ---------------------------------------------------------------------------

class TestStateSerializationRoundtrip:
    def test_roundtrip_empty_state(self):
        state = default_state()
        data = _state_to_dict(state)
        restored = _state_from_dict(data)
        assert restored.source_path == state.source_path
        assert restored.global_install is None
        assert restored.local_installs == {}

    def test_roundtrip_with_memory_config(self):
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={},
            memory=MemoryConfig(backend="obsidian", path="/vault/notes"),
        )
        data = _state_to_dict(state)
        restored = _state_from_dict(data)
        assert restored.memory.backend == "obsidian"
        assert restored.memory.path == "/vault/notes"

    def test_missing_memory_key_defaults_to_local(self):
        data = {
            "source_path": "",
            "source_commit": "",
            "global": None,
            "local": {},
            # No "memory" key
        }
        restored = _state_from_dict(data)
        assert restored.memory.backend == "local"

    def test_state_roundtrip_includes_memory_migrations(self):
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={},
            memory_migrations=MigrationState(completed=["v1"]),
        )
        data = _state_to_dict(state)
        restored = _state_from_dict(data)
        assert restored.memory_migrations.completed == ["v1"]

    def test_state_from_dict_missing_migrations_defaults_empty(self):
        data = {
            "source_path": "",
            "source_commit": "",
            "global": None,
            "local": {},
        }
        restored = _state_from_dict(data)
        assert restored.memory_migrations.completed == []

    def test_roundtrip_with_backend_state_and_installed_items(self):
        backend_state = BackendState(
            role_models={"lead": "claude-opus-4"},
            installed={
                "agents": {
                    "lead.md": InstalledItem(sha="abc123", target="/path/to/lead.md", mode="symlink")
                }
            },
        )
        scope = ScopeState(
            installed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            mode="symlink",
            installed_version="2.0.0",
            clis={"claude": backend_state},
        )
        state = State(
            source_path="/src",
            source_commit="deadbeef",
            global_install=scope,
            local_installs={},
        )
        data = _state_to_dict(state)
        restored = _state_from_dict(data)
        assert restored.global_install is not None
        assert "claude" in restored.global_install.clis
        claude_state = restored.global_install.clis["claude"]
        assert "agents" in claude_state.installed
        assert "lead.md" in claude_state.installed["agents"]
        item = claude_state.installed["agents"]["lead.md"]
        assert item.sha == "abc123"
        assert item.mode == "symlink"
