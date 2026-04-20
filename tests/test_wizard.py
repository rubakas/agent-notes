"""Test wizard module."""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import agent_notes.wizard as wizard


class TestSafeInput:
    """Test _safe_input helper function."""

    def test_normal_input(self):
        with patch('builtins.input', return_value='  hello  '):
            result = wizard._safe_input("Enter: ")
            assert result == "hello"

    def test_empty_input_with_default(self):
        with patch('builtins.input', return_value=''):
            result = wizard._safe_input("Enter: ", "default")
            assert result == "default"

    def test_empty_input_no_default(self):
        with patch('builtins.input', return_value=''):
            result = wizard._safe_input("Enter: ")
            assert result == ""

    def test_keyboard_interrupt(self, capsys):
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit):
                wizard._safe_input("Enter: ")
        captured = capsys.readouterr()
        assert "Installation cancelled." in captured.out

    def test_eof_error(self, capsys):
        with patch('builtins.input', side_effect=EOFError):
            with pytest.raises(SystemExit):
                wizard._safe_input("Enter: ")
        captured = capsys.readouterr()
        assert "Installation cancelled." in captured.out


class TestCanInteractive:
    """Test _can_interactive function."""

    def test_non_tty_returns_false(self):
        with patch('sys.stdin') as mock_stdin:
            mock_stdin.isatty.return_value = False
            assert not wizard._can_interactive()

    def test_no_termios_returns_false(self):
        with patch.object(wizard, '_HAS_TTY', False):
            assert not wizard._can_interactive()


class TestCheckboxSelect:
    """Test _checkbox_select function."""

    def test_non_interactive_returns_defaults(self):
        """Should return defaults when not interactive."""
        with patch.object(wizard, '_can_interactive', return_value=False):
            options = [("A", "a"), ("B", "b")]
            result = wizard._checkbox_select("Title", options, defaults={"a"})
            assert result == {"a"}

    def test_non_interactive_returns_all_when_no_defaults(self):
        """Should return all values when defaults is None."""
        with patch.object(wizard, '_can_interactive', return_value=False):
            options = [("A", "a"), ("B", "b")]
            result = wizard._checkbox_select("Title", options)
            assert result == {"a", "b"}


class TestRadioSelect:
    """Test _radio_select function."""

    def test_non_interactive_returns_default(self):
        """Should return default value when not interactive."""
        with patch.object(wizard, '_can_interactive', return_value=False):
            options = [("A", "a"), ("B", "b")]
            result = wizard._radio_select("Title", options, default=1)
            assert result == "b"

    def test_non_interactive_returns_first_by_default(self):
        with patch.object(wizard, '_can_interactive', return_value=False):
            options = [("A", "a"), ("B", "b")]
            result = wizard._radio_select("Title", options)
            assert result == "a"


class TestCheckboxSelectFallback:
    """Test _checkbox_select_fallback function."""

    def test_empty_input_returns_defaults(self):
        with patch('builtins.input', return_value=''):
            options = [("A", "a"), ("B", "b")]
            result = wizard._checkbox_select_fallback("Title", options, defaults={"a"})
            assert result == {"a"}

    def test_toggle_selection(self):
        with patch('builtins.input', return_value='1'):
            options = [("A", "a"), ("B", "b")]
            result = wizard._checkbox_select_fallback("Title", options, defaults={"a", "b"})
            # Toggling 1 removes "a" from defaults
            assert result == {"b"}

    def test_toggle_add(self):
        with patch('builtins.input', return_value='2'):
            options = [("A", "a"), ("B", "b")]
            result = wizard._checkbox_select_fallback("Title", options, defaults={"a"})
            assert result == {"a", "b"}


class TestRadioSelectFallback:
    """Test _radio_select_fallback function."""

    def test_default_selection(self):
        with patch('builtins.input', return_value=''):
            options = [("A", "a"), ("B", "b")]
            result = wizard._radio_select_fallback("Title", options, default=0)
            assert result == "a"

    def test_choose_second(self):
        with patch('builtins.input', return_value='2'):
            options = [("A", "a"), ("B", "b")]
            result = wizard._radio_select_fallback("Title", options, default=0)
            assert result == "b"

    def test_invalid_falls_back_to_default(self):
        with patch('builtins.input', return_value='abc'):
            options = [("A", "a"), ("B", "b")]
            result = wizard._radio_select_fallback("Title", options, default=1)
            assert result == "b"


class TestGetSkillGroups:
    """Test _get_skill_groups function."""

    def test_no_skills_dir(self, monkeypatch):
        fake_skills_dir = Path("/nonexistent")
        monkeypatch.setattr(wizard, 'DIST_SKILLS_DIR', fake_skills_dir)
        result = wizard._get_skill_groups()
        assert result == {}

    def test_mixed_skills(self, tmp_path, monkeypatch):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "rails-models").mkdir()
        (skills_dir / "rails-controllers").mkdir()
        (skills_dir / "rails-kamal").mkdir()
        (skills_dir / "docker-compose").mkdir()
        (skills_dir / "docker-dockerfile").mkdir()
        (skills_dir / "git").mkdir()
        (skills_dir / "other-skill").mkdir()

        monkeypatch.setattr(wizard, 'DIST_SKILLS_DIR', skills_dir)
        result = wizard._get_skill_groups()

        expected = {
            "Rails": ["rails-controllers", "rails-models"],
            "Docker": ["docker-compose", "docker-dockerfile"],
            "Kamal": ["rails-kamal"],
            "Git": ["git"]
        }
        assert result.keys() == expected.keys()
        for key in expected:
            assert set(result[key]) == set(expected[key])

    def test_empty_skills_dir(self, tmp_path, monkeypatch):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        monkeypatch.setattr(wizard, 'DIST_SKILLS_DIR', skills_dir)
        result = wizard._get_skill_groups()
        assert result == {}

    def test_only_files_no_dirs(self, tmp_path, monkeypatch):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "rails-models.txt").write_text("content")
        (skills_dir / "docker-compose.md").write_text("content")
        monkeypatch.setattr(wizard, 'DIST_SKILLS_DIR', skills_dir)
        result = wizard._get_skill_groups()
        assert result == {}


class TestCountRules:
    """Test _count_rules function."""

    def test_no_rules_dir(self, monkeypatch):
        fake_rules_dir = Path("/nonexistent")
        monkeypatch.setattr(wizard, 'DIST_RULES_DIR', fake_rules_dir)
        result = wizard._count_rules()
        assert result == 0

    def test_count_markdown_files(self, tmp_path, monkeypatch):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule1.md").write_text("content")
        (rules_dir / "rule2.md").write_text("content")
        (rules_dir / "readme.txt").write_text("content")
        (rules_dir / "config.json").write_text("{}")
        monkeypatch.setattr(wizard, 'DIST_RULES_DIR', rules_dir)
        result = wizard._count_rules()
        assert result == 2

    def test_empty_rules_dir(self, tmp_path, monkeypatch):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        monkeypatch.setattr(wizard, 'DIST_RULES_DIR', rules_dir)
        result = wizard._count_rules()
        assert result == 0


class TestSelectCli:
    """Test _select_cli function (non-interactive fallback)."""

    def test_defaults_both(self, capsys):
        """Non-interactive returns both CLIs by default."""
        with patch.object(wizard, '_can_interactive', return_value=False):
            with patch.object(wizard, '_checkbox_select_fallback', return_value={"claude", "opencode"}):
                result = wizard._select_cli()
                assert result == {"claude", "opencode"}

    def test_claude_only(self, capsys):
        with patch.object(wizard, '_can_interactive', return_value=False):
            with patch.object(wizard, '_checkbox_select_fallback', return_value={"claude"}):
                result = wizard._select_cli()
                assert result == {"claude"}
        captured = capsys.readouterr()
        assert "Claude Code" in captured.out


class TestSelectScope:
    """Test _select_scope function."""

    def test_global_default(self, capsys):
        with patch.object(wizard, '_can_interactive', return_value=False):
            with patch.object(wizard, '_radio_select_fallback', return_value="global"):
                result = wizard._select_scope()
                assert result == "global"
        captured = capsys.readouterr()
        assert "Global" in captured.out

    def test_local(self, capsys):
        with patch.object(wizard, '_can_interactive', return_value=False):
            with patch.object(wizard, '_radio_select_fallback', return_value="local"):
                result = wizard._select_scope()
                assert result == "local"
        captured = capsys.readouterr()
        assert "Local" in captured.out


class TestSelectMode:
    """Test _select_mode function."""

    def test_symlink_default(self, capsys):
        with patch.object(wizard, '_can_interactive', return_value=False):
            with patch.object(wizard, '_radio_select_fallback', return_value="symlink"):
                result = wizard._select_mode()
                assert result is False
        captured = capsys.readouterr()
        assert "Symlink" in captured.out

    def test_copy(self, capsys):
        with patch.object(wizard, '_can_interactive', return_value=False):
            with patch.object(wizard, '_radio_select_fallback', return_value="copy"):
                result = wizard._select_mode()
                assert result is True
        captured = capsys.readouterr()
        assert "Copy" in captured.out


class TestSelectSkills:
    """Test _select_skills function."""

    def test_no_skill_groups(self):
        with patch.object(wizard, '_get_skill_groups', return_value={}):
            result = wizard._select_skills()
            assert result == []

    def test_all_selected_by_default(self, capsys):
        mock_groups = {
            "Rails": ["rails-models", "rails-controllers"],
            "Docker": ["docker-compose"]
        }
        with patch.object(wizard, '_get_skill_groups', return_value=mock_groups):
            with patch.object(wizard, '_can_interactive', return_value=False):
                with patch.object(wizard, '_checkbox_select_fallback', return_value={"Rails", "Docker"}):
                    result = wizard._select_skills()
                    assert set(result) == {"rails-models", "rails-controllers", "docker-compose"}
        captured = capsys.readouterr()
        assert "Rails (2)" in captured.out
        assert "Docker (1)" in captured.out

    def test_partial_selection(self, capsys):
        mock_groups = {
            "Rails": ["rails-models", "rails-controllers"],
            "Docker": ["docker-compose"],
            "Git": ["git"]
        }
        with patch.object(wizard, '_get_skill_groups', return_value=mock_groups):
            with patch.object(wizard, '_can_interactive', return_value=False):
                with patch.object(wizard, '_checkbox_select_fallback', return_value={"Rails"}):
                    result = wizard._select_skills()
                    assert set(result) == {"rails-models", "rails-controllers"}


class TestConfirmInstall:
    """Test _confirm_install function."""

    def test_confirm_yes(self, capsys):
        with patch.object(wizard, '_get_skill_groups', return_value={}):
            with patch.object(wizard, '_count_rules', return_value=5):
                with patch('agent_notes.install.count_agents_claude', return_value=3):
                    with patch('agent_notes.install.count_agents_opencode', return_value=2):
                        with patch('builtins.input', return_value='Y'):
                            result = wizard._confirm_install({"claude"}, "global", False, [])
                            assert result is True

    def test_confirm_no(self, capsys):
        with patch.object(wizard, '_get_skill_groups', return_value={}):
            with patch.object(wizard, '_count_rules', return_value=5):
                with patch('agent_notes.install.count_agents_claude', return_value=3):
                    with patch('agent_notes.install.count_agents_opencode', return_value=2):
                        with patch('builtins.input', return_value='n'):
                            result = wizard._confirm_install({"claude"}, "global", False, [])
                            assert result is False

    def test_confirm_default_yes(self, capsys):
        with patch.object(wizard, '_get_skill_groups', return_value={}):
            with patch.object(wizard, '_count_rules', return_value=5):
                with patch('agent_notes.install.count_agents_claude', return_value=3):
                    with patch('agent_notes.install.count_agents_opencode', return_value=2):
                        with patch('builtins.input', return_value=''):
                            result = wizard._confirm_install({"claude"}, "global", False, [])
                            assert result is True

    def test_display_summary_both_clis(self, capsys):
        with patch.object(wizard, '_get_skill_groups', return_value={}):
            with patch.object(wizard, '_count_rules', return_value=5):
                with patch('agent_notes.install.count_agents_claude', return_value=3):
                    with patch('agent_notes.install.count_agents_opencode', return_value=2):
                        with patch('builtins.input', return_value='Y'):
                            wizard._confirm_install({"claude", "opencode"}, "global", False, [])
        captured = capsys.readouterr()
        assert "CLI:      Claude Code + OpenCode" in captured.out

    def test_display_summary_skills(self, capsys):
        mock_groups = {
            "Rails": ["rails-models", "rails-controllers"],
            "Docker": ["docker-compose"]
        }
        selected_skills = ["rails-models", "docker-compose"]
        with patch.object(wizard, '_get_skill_groups', return_value=mock_groups):
            with patch.object(wizard, '_count_rules', return_value=5):
                with patch('agent_notes.install.count_agents_claude', return_value=3):
                    with patch('agent_notes.install.count_agents_opencode', return_value=2):
                        with patch('builtins.input', return_value='Y'):
                            wizard._confirm_install({"claude"}, "global", False, selected_skills)
        captured = capsys.readouterr()
        assert "Skills:   Rails (1), Docker (1)" in captured.out


class TestInstallSkillsFiltered:
    """Test install_skills_filtered function."""

    def test_no_skills(self, tmp_path):
        target = tmp_path / "target"
        wizard.install_skills_filtered([], [target], False)
        assert not target.exists()

    def test_no_skills_dir(self, tmp_path, monkeypatch):
        fake_skills_dir = Path("/nonexistent")
        monkeypatch.setattr(wizard, 'DIST_SKILLS_DIR', fake_skills_dir)
        target = tmp_path / "target"
        wizard.install_skills_filtered(["rails-models"], [target], False)
        assert not target.exists()

    def test_install_selected_skills(self, tmp_path, monkeypatch, capsys):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "rails-models").mkdir()
        (skills_dir / "rails-models" / "SKILL.md").write_text("models content")
        (skills_dir / "docker-compose").mkdir()
        (skills_dir / "docker-compose" / "SKILL.md").write_text("docker content")
        (skills_dir / "rails-controllers").mkdir()
        (skills_dir / "rails-controllers" / "SKILL.md").write_text("controllers content")

        monkeypatch.setattr(wizard, 'DIST_SKILLS_DIR', skills_dir)

        with patch('agent_notes.wizard.place_file') as mock_place:
            targets = [tmp_path / "target1", tmp_path / "target2"]
            wizard.install_skills_filtered(["rails-models", "docker-compose"], targets, True)
            assert mock_place.call_count == 4

        captured = capsys.readouterr()
        assert "Installing skills to" in captured.out


class TestInstallAgentsFiltered:
    """Test install_agents_filtered function."""

    def test_claude_global(self, capsys):
        with patch('agent_notes.wizard.place_dir_contents') as mock_place:
            wizard.install_agents_filtered({"claude"}, "global", False)
            mock_place.assert_called_once()
            args = mock_place.call_args[0]
            assert "agents" in str(args[0])
            assert "agents" in str(args[1])
        captured = capsys.readouterr()
        assert "Installing Claude Code agents to ~/.claude/agents/" in captured.out

    def test_opencode_local(self, capsys):
        with patch('agent_notes.wizard.place_dir_contents') as mock_place:
            wizard.install_agents_filtered({"opencode"}, "local", True)
            mock_place.assert_called_once()
            args = mock_place.call_args[0]
            assert "agents" in str(args[0])
            assert ".opencode/agents" in str(args[1])
        captured = capsys.readouterr()
        assert "Installing OpenCode agents to .opencode/agents/" in captured.out

    def test_both_clis(self, capsys):
        with patch('agent_notes.wizard.place_dir_contents') as mock_place:
            wizard.install_agents_filtered({"claude", "opencode"}, "global", False)
            assert mock_place.call_count == 2
        captured = capsys.readouterr()
        assert "Claude Code agents" in captured.out
        assert "OpenCode agents" in captured.out


class TestInstallConfigFiltered:
    """Test install_config_filtered function."""

    def test_claude_global(self, tmp_path, monkeypatch, capsys):
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("claude config")
        dist_rules = tmp_path / "dist" / "rules"
        dist_rules.mkdir(parents=True)
        (dist_rules / "safety.md").write_text("rule")

        monkeypatch.setattr(wizard, 'DIST_CLAUDE_DIR', dist_claude)
        monkeypatch.setattr(wizard, 'DIST_RULES_DIR', dist_rules)

        with patch('agent_notes.wizard.place_file') as mock_place_file:
            with patch('agent_notes.wizard.place_dir_contents') as mock_place_dir:
                wizard.install_config_filtered({"claude"}, "global", False)
                assert mock_place_file.call_count >= 1
                assert mock_place_dir.call_count >= 1
        captured = capsys.readouterr()
        assert "Installing global config" in captured.out

    def test_opencode_local(self, tmp_path, monkeypatch, capsys):
        dist_opencode = tmp_path / "dist" / "opencode"
        dist_opencode.mkdir(parents=True)
        (dist_opencode / "AGENTS.md").write_text("agents config")
        monkeypatch.setattr(wizard, 'DIST_OPENCODE_DIR', dist_opencode)

        with patch('agent_notes.wizard.place_file') as mock_place_file:
            wizard.install_config_filtered({"opencode"}, "local", True)
            mock_place_file.assert_called()
        captured = capsys.readouterr()
        assert "Installing project rules" in captured.out

    def test_both_clis_local(self, tmp_path, monkeypatch, capsys):
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("claude config")
        dist_opencode = tmp_path / "dist" / "opencode"
        dist_opencode.mkdir(parents=True)
        (dist_opencode / "AGENTS.md").write_text("agents config")
        dist_rules = tmp_path / "dist" / "rules"
        dist_rules.mkdir(parents=True)

        monkeypatch.setattr(wizard, 'DIST_CLAUDE_DIR', dist_claude)
        monkeypatch.setattr(wizard, 'DIST_OPENCODE_DIR', dist_opencode)
        monkeypatch.setattr(wizard, 'DIST_RULES_DIR', dist_rules)

        with patch('agent_notes.wizard.place_file') as mock_place_file:
            with patch('agent_notes.wizard.place_dir_contents') as mock_place_dir:
                wizard.install_config_filtered({"claude", "opencode"}, "local", False)
                assert mock_place_file.call_count >= 2


class TestInteractiveInstall:
    """Test interactive_install function."""

    def test_full_wizard_happy_path(self, capsys):
        with patch.object(wizard, '_select_cli', return_value={"claude"}):
            with patch.object(wizard, '_select_scope', return_value="global"):
                with patch.object(wizard, '_select_mode', return_value=False):
                    with patch.object(wizard, '_select_skills', return_value=["rails-models"]):
                        with patch.object(wizard, '_confirm_install', return_value=True):
                            with patch('agent_notes.wizard.build') as mock_build:
                                with patch.object(wizard, 'install_skills_filtered') as mock_skills:
                                    with patch.object(wizard, 'install_agents_filtered') as mock_agents:
                                        with patch.object(wizard, 'install_config_filtered') as mock_config:
                                            with patch.object(wizard, 'get_version', return_value="1.0.0"):
                                                with patch.object(wizard, 'count_agents_claude', return_value=5):
                                                    with patch.object(wizard, 'count_skills', return_value=28):
                                                        with patch.object(wizard, '_count_rules', return_value=3):
                                                            wizard.interactive_install()

        mock_build.assert_called_once()
        mock_skills.assert_called_once()
        mock_agents.assert_called_once()
        mock_config.assert_called_once()

        captured = capsys.readouterr()
        assert "AgentNotes" in captured.out
        assert "v1.0.0" in captured.out
        assert "5 agents, 28 skills, and 3 rules" in captured.out
        assert "Building from source..." in captured.out
        assert "Done." in captured.out

    def test_no_cli_selected(self, capsys):
        with patch.object(wizard, '_select_cli', return_value=set()):
            with patch.object(wizard, 'get_version', return_value="1.0.0"):
                with patch.object(wizard, 'count_agents_claude', return_value=0):
                    with patch.object(wizard, 'count_skills', return_value=0):
                        with patch.object(wizard, '_count_rules', return_value=0):
                            wizard.interactive_install()
        captured = capsys.readouterr()
        assert "No CLI selected" in captured.out

    def test_installation_cancelled_by_user(self, capsys):
        with patch.object(wizard, '_select_cli', return_value={"claude"}):
            with patch.object(wizard, '_select_scope', return_value="global"):
                with patch.object(wizard, '_select_mode', return_value=False):
                    with patch.object(wizard, '_select_skills', return_value=[]):
                        with patch.object(wizard, '_confirm_install', return_value=False):
                            with patch.object(wizard, 'get_version', return_value="1.0.0"):
                                with patch.object(wizard, 'count_agents_claude', return_value=0):
                                    with patch.object(wizard, 'count_skills', return_value=0):
                                        with patch.object(wizard, '_count_rules', return_value=0):
                                            wizard.interactive_install()
        captured = capsys.readouterr()
        assert "Installation cancelled." in captured.out

    def test_build_failure(self, capsys):
        with patch.object(wizard, '_select_cli', return_value={"claude"}):
            with patch.object(wizard, '_select_scope', return_value="global"):
                with patch.object(wizard, '_select_mode', return_value=False):
                    with patch.object(wizard, '_select_skills', return_value=[]):
                        with patch.object(wizard, '_confirm_install', return_value=True):
                            with patch('agent_notes.wizard.build', side_effect=Exception("Build error")):
                                with patch.object(wizard, 'get_version', return_value="1.0.0"):
                                    with patch.object(wizard, 'count_agents_claude', return_value=0):
                                        with patch.object(wizard, 'count_skills', return_value=0):
                                            with patch.object(wizard, '_count_rules', return_value=0):
                                                wizard.interactive_install()
        captured = capsys.readouterr()
        assert "Build failed: Build error" in captured.out
