"""Tests that all 4 registries load correctly from their source files."""
import pytest

from agent_notes.registries.model_registry import load_model_registry
from agent_notes.registries.role_registry import load_role_registry
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.registries.agent_registry import load_agent_registry


# --- Model registry ---

def test_model_registry_loads():
    registry = load_model_registry()
    assert len(registry.all()) > 0


def test_model_has_required_fields():
    registry = load_model_registry()
    for model in registry.all():
        assert model.id, f"Model missing id"
        assert model.label, f"Model {model.id} missing label"
        assert model.family, f"Model {model.id} missing family"
        assert model.model_class, f"Model {model.id} missing model_class"
        assert model.aliases is not None, f"Model {model.id} missing aliases"


def test_newest_model_per_class_is_not_deprecated():
    """For every model_class present in the catalog, the newest entry must not be
    deprecated — the catalog must always expose a deployable option per class."""
    from agent_notes.registries.model_registry import _natural_key

    registry = load_model_registry()
    by_class: dict = {}
    for model in registry.all():
        by_class.setdefault(model.model_class, []).append(model)

    for cls, models in by_class.items():
        newest = sorted(models, key=lambda m: _natural_key(m.id))[-1]
        assert not newest.deprecated, (
            f"Newest model in class '{cls}' ({newest.id}) is deprecated — "
            f"the catalog must have at least one non-deprecated option per class"
        )


def test_every_role_class_has_at_least_one_non_deprecated_model():
    """For each class a role needs (role.typical_class), at least one non-deprecated
    model must exist in the catalog. Without this guard, the wizard falls back to
    an arbitrary model for that role instead of its intended class."""
    model_registry = load_model_registry()
    role_registry = load_role_registry()

    non_deprecated_classes = {
        m.model_class for m in model_registry.all() if not m.deprecated
    }

    for role in role_registry.all():
        assert role.typical_class in non_deprecated_classes, (
            f"Role '{role.name}' requires model_class '{role.typical_class}' but no "
            f"non-deprecated model of that class exists in the catalog "
            f"(available non-deprecated classes: {sorted(non_deprecated_classes)})"
        )


def test_model_aliases_are_exact_version_strings_not_class_names():
    """Guard: an alias like anthropic: 'haiku' would render a pinned model as a
    bare class name in frontmatter, letting the harness substitute its own
    default version. Every alias must differ from the bare model_class."""
    registry = load_model_registry()
    for model in registry.all():
        for provider, alias in model.aliases.items():
            assert alias != model.model_class, (
                f"Model {model.id}: alias for provider '{provider}' is the bare "
                f"class name {alias!r} — use the exact model version string"
            )


def test_natural_sort_orders_version_numbers_numerically():
    """_natural_key must place claude-opus-4-10 after claude-opus-4-8.

    Without natural sort, lexicographic ordering puts '4-10' before '4-8'
    because '1' < '8', causing the resolver to pick an older model as 'newest'.
    """
    from agent_notes.registries.model_registry import _natural_key

    ids = ["claude-opus-4-8", "claude-opus-4-10", "claude-opus-4-6"]
    result = sorted(ids, key=_natural_key)
    assert result.index("claude-opus-4-10") > result.index("claude-opus-4-8"), (
        f"Expected claude-opus-4-10 after claude-opus-4-8 in natural sort, got: {result}"
    )


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


def test_role_registry_loads_typical_effort():
    registry = load_role_registry()
    assert registry.get("orchestrator").typical_effort == "high"
    assert registry.get("reasoner").typical_effort == "high"
    assert registry.get("worker").typical_effort == "medium"
    assert registry.get("scout").typical_effort == "low"


def test_role_registry_loads_order():
    """Canonical display order: orchestrator → reasoner → worker → scout."""
    registry = load_role_registry()
    assert registry.get("orchestrator").order == 1
    assert registry.get("reasoner").order == 2
    assert registry.get("worker").order == 3
    assert registry.get("scout").order == 4


def test_role_order_defaults_to_last_when_missing(tmp_path):
    """Roles without an explicit order sort after all ordered roles."""
    from agent_notes.domain.role import DEFAULT_ROLE_ORDER
    (tmp_path / "custom.yaml").write_text(
        "name: custom\nlabel: Custom\ndescription: d\ntypical_class: sonnet\n"
    )
    registry = load_role_registry(tmp_path)
    assert registry.get("custom").order == DEFAULT_ROLE_ORDER


# --- Skill registry ---

def test_skill_registry_loads():
    registry = load_skill_registry()
    assert len(registry.all()) >= 15


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


def test_ingest_skill_has_requires_memory():
    registry = load_skill_registry()
    ingest = registry.get("ingest")
    assert ingest.requires_memory is not None, "ingest skill should have requires_memory set"
    backends = {b.strip() for b in ingest.requires_memory.split(",")}
    assert "obsidian" in backends, "ingest skill requires_memory should include obsidian"


def test_requires_memory_normalized_no_spaces():
    """requires_memory with spaces after commas is normalized to canonical form (no spaces)."""
    from pathlib import Path
    import tempfile, textwrap

    skill_md_content = textwrap.dedent("""\
        ---
        name: test-skill
        description: "A test skill."
        group: process
        requires_memory: obsidian, local
        ---

        # Test Skill
    """)

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(skill_md_content)

        registry = load_skill_registry(skills_dir=Path(tmpdir))
        skill = registry.get("test-skill")

    assert skill.requires_memory == "obsidian,local", (
        f"expected 'obsidian,local' but got '{skill.requires_memory}'"
    )


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
