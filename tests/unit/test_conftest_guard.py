"""The suite never reaches the developer's real home (tests/conftest.py)."""
import os
import pwd
from pathlib import Path

import pytest

import agent_notes.config as config
from agent_notes.services.user_config import config_path

REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)


@pytest.mark.parametrize("name", ["AGENTS_HOME", "MEMORY_DIR", "BACKUP_DIR", "BIN_HOME",
                                  "CLAUDE_HOME", "OPENCODE_HOME", "GITHUB_HOME"])
def test_home_derived_constants_point_at_scratch(name):
    assert not Path(getattr(config, name)).is_relative_to(REAL_HOME), name


def test_xdg_config_home_is_scratch():
    assert not Path(os.environ["XDG_CONFIG_HOME"]).is_relative_to(REAL_HOME)
    assert not config_path().is_relative_to(REAL_HOME)


def test_home_is_scratch():
    assert not Path.home().is_relative_to(REAL_HOME)
