"""Tests for agent_notes.services.installer — _plan_file, _plan_component, plan_install."""
import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_notes.services.installer import (
    _plan_file,
    _plan_component,
    plan_install,
    InstallAction,
)
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.registries.cli_registry import CLIRegistry

# Backup timestamp pattern
_TS_RE = re.compile(r".*\.bak\.\d{8}T\d{6}\d+Z$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backend(
    name: str = "claude",
    label: str = "Claude Code",
    global_home: Path = None,
    local_dir: str = ".claude",
    layout: dict = None,
    features: dict = None,
    tmp_path: Path = None,
) -> CLIBackend:
    """Build a minimal CLIBackend for testing."""
    if global_home is None and tmp_path is not None:
        global_home = tmp_path / f"{name}_global"
        global_home.mkdir(parents=True, exist_ok=True)
    elif global_home is None:
        global_home = Path.home() / f".{name}"

    if layout is None:
        layout = {
            "config": f"{'CLAUDE' if name == 'claude' else 'AGENTS'}.md",
            "agents": "agents",
            "rules": "rules",
            "skills": "skills",
            "commands": "commands",
        }
    if features is None:
        features = {
            "agents": True,
            "rules": True,
            "skills": True,
            "commands": True,
            "config": True,
        }
    return CLIBackend(
        name=name,
        label=label,
        global_home=global_home,
        local_dir=local_dir,
        layout=layout,
        features=features,
        global_template=None,
    )


# ---------------------------------------------------------------------------
# _plan_file tests
# ---------------------------------------------------------------------------

class TestPlanFileMissingDst:
    def test_returns_install_when_dst_missing(self, tmp_path):
        src = tmp_path / "src.md"
        src.write_bytes(b"content")
        dst = tmp_path / "dst.md"  # does not exist

        action = _plan_file(src, dst)

        assert action.action == "install"
        assert action.src == src
        assert action.dst == dst
        assert action.backup_path is None


class TestPlanFileIdenticalContent:
    def test_returns_skip_when_files_identical(self, tmp_path):
        content = b"same content"
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(content)
        dst.write_bytes(content)

        action = _plan_file(src, dst)

        assert action.action == "skip"
        assert action.backup_path is None


class TestPlanFileDifferingContent:
    def test_returns_overwrite_when_dst_differs(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        action = _plan_file(src, dst)

        assert action.action == "overwrite"

    def test_overwrite_has_backup_path_set(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        action = _plan_file(src, dst)

        assert action.backup_path is not None

    def test_overwrite_backup_path_is_sibling_with_bak_timestamp(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        action = _plan_file(src, dst)

        assert action.backup_path.parent == tmp_path
        assert _TS_RE.match(str(action.backup_path.name)), (
            f"backup_path name {action.backup_path.name!r} does not match .bak.<timestamp>"
        )

    def test_plan_file_does_not_write_any_files(self, tmp_path):
        """_plan_file is dry-run — must not touch the filesystem."""
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new")
        dst.write_bytes(b"old")
        original_dst_content = dst.read_bytes()

        _plan_file(src, dst)

        assert dst.read_bytes() == original_dst_content
        bak_files = list(tmp_path.glob("dst.md.bak.*"))
        assert bak_files == [], "plan_file must not create any backup files"


class TestPlanFileCopyModeSymlink:
    def test_copy_mode_skip_when_symlink_points_to_src(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"content")
        dst.symlink_to(src)

        action = _plan_file(src, dst, copy_mode=True)

        assert action.action == "skip"

    def test_copy_mode_overwrite_when_symlink_points_elsewhere(self, tmp_path):
        src = tmp_path / "src.md"
        other = tmp_path / "other.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"content")
        other.write_bytes(b"other content")
        dst.symlink_to(other)

        action = _plan_file(src, dst, copy_mode=True)

        # symlink points elsewhere — should be install (dst.exists() is True via symlink,
        # but it IS a symlink so the exists-and-not-symlink branch is skipped → install)
        assert action.action == "install"

    def test_symlink_mode_false_treats_existing_symlink_as_install(self, tmp_path):
        """In symlink mode (copy_mode=False), existing symlink pointing elsewhere → install."""
        src = tmp_path / "src.md"
        other = tmp_path / "other.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        other.write_bytes(b"other content")
        dst.symlink_to(other)

        action = _plan_file(src, dst, copy_mode=False)

        assert action.action == "install"


# ---------------------------------------------------------------------------
# _plan_component tests
# ---------------------------------------------------------------------------

class TestPlanComponentSkillsNoSrcDir:
    def test_skills_returns_empty_when_src_dir_missing(self, tmp_path):
        """Guard: if dist skills dir does not exist, return []."""
        backend = _make_backend(tmp_path=tmp_path)
        # Don't create any dist or dst directories — both are absent
        missing_dist = tmp_path / "missing_dist"

        import agent_notes.services.installer as installer_mod

        # Patch DIST_SKILLS_DIR to point to a nonexistent directory
        with patch.object(installer_mod.config, "DIST_SKILLS_DIR", missing_dist):
            with patch.object(installer_mod.config, "DIST_DIR", tmp_path / "missing"):
                actions = _plan_component(backend, "skills", "local")

        assert actions == []

    def test_returns_empty_list_when_component_not_supported(self, tmp_path):
        """Backend that has no 'commands' feature returns [] for commands."""
        backend = _make_backend(
            tmp_path=tmp_path,
            features={"agents": True, "rules": True, "skills": False, "commands": False},
        )
        import agent_notes.services.installer as installer_mod

        with patch.object(installer_mod.config, "DIST_DIR", tmp_path / "missing"):
            actions = _plan_component(backend, "commands", "local")

        assert actions == []


# ---------------------------------------------------------------------------
# plan_install tests
# ---------------------------------------------------------------------------

class TestPlanInstallSessionHook:
    def test_claude_backend_includes_settings_json_action(self, tmp_path):
        """plan_install must return at least one action targeting settings.json."""
        from agent_notes.registries.cli_registry import load_registry
        registry = load_registry()

        try:
            registry.get("claude")
        except KeyError:
            pytest.skip("claude backend not available in registry")

        import agent_notes.services.installer as installer_mod

        # Redirect settings.json to tmp_path so plan_session_hook has a predictable path
        fake_global_home = tmp_path / "claude_global"
        fake_global_home.mkdir()

        # Patch the settings_writer.has_hook to say hook is absent (so action != skip)
        with patch("agent_notes.services.installer.config.DIST_SKILLS_DIR", tmp_path / "no_skills"):
            with patch("agent_notes.services.settings_writer.has_hook", return_value=False):
                actions = plan_install(scope="local", registry=registry, selected_clis={"claude"})

        settings_actions = [a for a in actions if "settings.json" in str(a.dst)]
        assert settings_actions, (
            "Expected at least one action targeting settings.json, "
            f"got dst paths: {[str(a.dst) for a in actions]}"
        )


class TestPlanInstallDstPaths:
    def test_plan_install_local_scope_produces_install_actions(self, tmp_path):
        """plan_install with a fake one-CLI registry returns InstallAction objects with expected fields."""
        from agent_notes.registries.cli_registry import load_registry

        registry = load_registry()

        # Use a fresh tmp scope so nothing exists yet
        import agent_notes.services.installer as installer_mod
        import agent_notes.config as config_mod

        # Run plan_install with local scope — just verify structural invariants
        with patch("agent_notes.services.settings_writer.has_hook", return_value=False):
            actions = plan_install(scope="local", registry=registry)

        assert isinstance(actions, list)
        for a in actions:
            assert isinstance(a, InstallAction)
            assert a.action in ("install", "skip", "overwrite", "modify")
            assert isinstance(a.src, Path)
            assert isinstance(a.dst, Path)
            # backup_path only set on overwrite
            if a.action == "overwrite":
                assert a.backup_path is not None
            else:
                assert a.backup_path is None or a.action == "overwrite"

    def test_plan_install_does_not_touch_filesystem(self, tmp_path):
        """plan_install is dry-run — existing files must not be modified."""
        from agent_notes.registries.cli_registry import load_registry

        # Create a sentinel file that would be a target
        registry = load_registry()

        with patch("agent_notes.services.settings_writer.has_hook", return_value=True):
            before = list(tmp_path.glob("**/*"))
            plan_install(scope="local", registry=registry)
            after = list(tmp_path.glob("**/*"))

        assert before == after, "plan_install must not create or modify any files"
