"""Tests that all 4 registries load correctly from their source files."""
import pytest

from agent_notes.registries.model_registry import load_model_registry
from agent_notes.registries.role_registry import load_role_registry
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.registries.agent_registry import load_agent_registry


# --- Model registry ---

def test_model_registry_loads():
    registry = load_model_registry()
    assert len(registry.all()) >= 8


def test_model_registry_includes_opus():
    registry = load_model_registry()
    ids = registry.ids()
    assert "claude-opus-4-7" in ids


def test_model_registry_includes_sonnet():
    registry = load_model_registry()
    ids = registry.ids()
    assert "claude-sonnet-4-6" in ids


def test_model_registry_includes_haiku():
    registry = load_model_registry()
    ids = registry.ids()
    assert "claude-haiku-4-5" in ids


def test_model_has_required_fields():
    registry = load_model_registry()
    for model in registry.all():
        assert model.id, f"Model missing id"
        assert model.label, f"Model {model.id} missing label"
        assert model.family, f"Model {model.id} missing family"
        assert model.model_class, f"Model {model.id} missing model_class"
        assert model.aliases is not None, f"Model {model.id} missing aliases"


# --- Role registry ---

def test_role_registry_loads():
    registry = load_role_registry()
    assert len(registry.all()) >= 3


def test_role_registry_has_orchestrator():
    registry = load_role_registry()
    names = registry.names()
    assert "orchestrator" in names


def test_role_registry_has_worker():
    registry = load_role_registry()
    names = registry.names()
    assert "worker" in names


def test_role_registry_has_scout():
    registry = load_role_registry()
    names = registry.names()
    assert "scout" in names


def test_role_has_required_fields():
    registry = load_role_registry()
    for role in registry.all():
        assert role.name, f"Role missing name"
        assert role.label, f"Role {role.name} missing label"


# --- Skill registry ---

def test_skill_registry_loads():
    registry = load_skill_registry()
    assert len(registry.all()) >= 30


def test_skill_registry_includes_git():
    registry = load_skill_registry()
    assert "git" in registry.names()


def test_skill_registry_includes_brainstorming():
    registry = load_skill_registry()
    assert "brainstorming" in registry.names()


def test_skill_has_required_fields():
    registry = load_skill_registry()
    for skill in registry.all():
        assert skill.name, f"Skill missing name"
        assert skill.description, f"Skill {skill.name} missing description"
        assert skill.group, f"Skill {skill.name} missing group"


# --- Agent registry ---

def test_agent_registry_loads():
    registry = load_agent_registry()
    assert len(registry.all()) >= 15


def test_agent_registry_includes_coder():
    registry = load_agent_registry()
    assert "coder" in registry.names()


def test_agent_registry_includes_reviewer():
    registry = load_agent_registry()
    assert "reviewer" in registry.names()


def test_agent_registry_includes_explorer():
    registry = load_agent_registry()
    assert "explorer" in registry.names()


def test_agent_has_required_fields():
    registry = load_agent_registry()
    for agent in registry.all():
        assert agent.name, f"Agent missing name (id)"
        assert agent.description, f"Agent {agent.name} missing description"
