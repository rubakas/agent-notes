"""The review's confirmation counts what the install will remove (spec 007 FR-A11, T04 follow-up)."""
import pytest

import agent_notes.commands.wizard.orchestrator as orchestrator
from agent_notes.commands.wizard.review import InstallChoices
from agent_notes.registries.cli_registry import load_registry
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _choices(world, skills):
    choices = InstallChoices()
    choices.clis = {"claude"}
    choices.skills = list(skills)
    return choices


def test_the_question_says_how_many_files_are_removed(world):
    world.use("main")
    world.wizard()
    dropped = len(world.skills()) - 2

    question, _lines = orchestrator._plan_summary(_choices(world, world.skills()[:2]), load_registry())

    assert question.endswith(f"backed up, {dropped * 2} removed)?")
    assert question.startswith("Install ")
    assert len(question) < 60


def test_a_zero_is_left_out(world):
    world.use("main")
    world.wizard()

    question, _lines = orchestrator._plan_summary(_choices(world, world.skills()), load_registry())

    assert question.endswith("backed up)?") and "removed" not in question


def test_a_first_install_removes_nothing(world):
    world.use("main")

    question, _lines = orchestrator._plan_summary(_choices(world, world.skills()), load_registry())

    assert "removed" not in question
