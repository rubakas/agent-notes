"""The command that re-renders THIS install after a failed regenerate."""
from pathlib import Path

from agent_notes.commands.regenerate import regenerate_instruction


def test_global_install():
    assert regenerate_instruction("global", None, "") == "agent-notes regenerate"


def test_global_profile():
    assert regenerate_instruction("global", None, "work") == "agent-notes regenerate --profile work"


def test_local_install():
    assert (regenerate_instruction("local", Path("/p/app"), "")
            == "cd /p/app && agent-notes regenerate --local")


def test_local_profile_and_a_path_with_spaces():
    assert (regenerate_instruction("local", Path("/p/my app"), "work")
            == "cd '/p/my app' && agent-notes regenerate --local --profile work")
