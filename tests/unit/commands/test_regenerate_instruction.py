"""The command that re-renders THIS install after a failed regenerate."""
import shlex
import sys
from pathlib import Path

import pytest

from agent_notes.cli import main
from agent_notes.commands.regenerate import regenerate_instruction


def test_global_install():
    assert regenerate_instruction("global", None, "") == "agent-notes regenerate"


def test_global_profile():
    assert regenerate_instruction("global", None, "work") == "agent-notes regenerate --profile=work"


def test_local_install():
    assert (regenerate_instruction("local", Path("/p/app"), "")
            == "cd /p/app && agent-notes regenerate --local")


def test_local_profile_and_a_path_with_spaces():
    assert (regenerate_instruction("local", Path("/p/my app"), "work")
            == "cd '/p/my app' && agent-notes regenerate --local --profile=work")


@pytest.mark.parametrize("scope, project", [("global", None), ("local", Path("/p/my app"))])
@pytest.mark.parametrize("label", ["-x", "my work", "a'b"])
def test_the_real_parser_reads_the_label_back(monkeypatch, scope, project, label):
    seen = {}
    monkeypatch.setattr("agent_notes.commands.regenerate.regenerate", lambda **kwargs: seen.update(kwargs))
    command = regenerate_instruction(scope, project, label).split(" && ")[-1]
    monkeypatch.setattr(sys, "argv", shlex.split(command))

    main()

    assert seen["profile_label"] == label
