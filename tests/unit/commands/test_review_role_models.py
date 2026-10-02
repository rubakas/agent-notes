"""Per-role choices for the review screen. ★ must be the resolver's own pick
(spec 005 SC-003) and offered efforts exactly what `config role-effort`
accepts (SC-004)."""
import pytest

from agent_notes.commands.config import compatible_models_for
from agent_notes.commands.wizard.role_models import (
    Catalog, edit_models, effort_options, model_items, recommended_choices,
    roles_for, set_model, starred_model,
)
from agent_notes.domain.model import Model
from agent_notes.domain.role import Role
from agent_notes.registries.cli_registry import load_registry
from agent_notes.registries.role_registry import load_role_registry
from agent_notes.services.model_resolver import select_model_for_role
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT
from tests.unit.tui.fakes import tui_session


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def _backend(name):
    return load_registry().get(name)


def _role(name):
    return load_role_registry().get(name)


def _agent_backends(catalog):
    return [b for b in load_registry().available()
            if b.supports("agents") and catalog.compatible(b)]


def test_claude_roles_leave_out_orchestrator_in_canonical_order():
    assert [r.name for r in roles_for(_backend("claude"))] == ["reasoner", "worker", "scout"]


def test_other_agent_backends_keep_orchestrator_first():
    assert [r.name for r in roles_for(_backend("codex"))] == [
        "orchestrator", "reasoner", "worker", "scout"]


def test_star_is_the_resolver_pick_for_every_backend_and_role(catalog):
    checked = 0
    for backend in _agent_backends(catalog):
        for role in roles_for(backend):
            expected, _ = select_model_for_role(compatible_models_for(backend), role, backend)
            star = starred_model(catalog, backend, role)
            assert (star and star.id) == (expected and expected.id), f"{backend.name}/{role.name}"
            checked += 1
    assert checked >= 11  # claude 3 + codex 4 + opencode 4


def test_effort_options_match_the_config_role_effort_checks(catalog, monkeypatch, capsys):
    from agent_notes.commands.config import _check_effort_valid
    from agent_notes.domain.state import BackendState, ScopeState
    from agent_notes.registries import cli_registry, model_registry, provider_registry

    clis = load_registry()
    providers = provider_registry.load_provider_registry()
    # _check_effort_valid reloads all three registries per call; serve them from memory.
    monkeypatch.setattr(model_registry, "load_model_registry", lambda *a, **k: catalog.registry)
    monkeypatch.setattr(cli_registry, "load_registry", lambda *a, **k: clis)
    monkeypatch.setattr(provider_registry, "load_provider_registry", lambda *a, **k: providers)
    vocabulary = {e for name in providers.names() for e in providers.get(name).efforts}
    for backend in _agent_backends(catalog):
        for model in catalog.compatible(backend):
            state = ScopeState(clis={backend.name: BackendState(role_models={"worker": model.id})})
            accepted = {e for e in vocabulary if _check_effort_valid(state, backend.name, "worker", e)}
            assert set(effort_options(backend, model)) == accepted, f"{backend.name}/{model.id}"
    capsys.readouterr()


def test_codex_offers_only_the_efforts_the_cli_accepts(catalog):
    codex = _backend("codex")
    gpt = next(m for m in catalog.compatible(codex) if m.family == "gpt")
    assert effort_options(codex, gpt) == ["minimal", "low", "medium", "high", "xhigh"]


def test_claude_offers_the_full_anthropic_vocabulary(catalog):
    assert effort_options(_backend("claude"), catalog.get("claude-opus-5-5")) == [
        "low", "medium", "high", "xhigh", "max"]


def test_a_model_without_effort_support_or_an_unknown_model_offers_none(catalog):
    claude = _backend("claude")
    assert effort_options(claude, catalog.get("claude-haiku-4-5")) == []
    assert effort_options(claude, catalog.get("claude-not-a-model")) == []


def test_recommended_choices_are_the_shipped_defaults(catalog):
    models, efforts = recommended_choices(catalog, _backend("claude"))
    assert models == {"reasoner": "claude-opus-5-5", "worker": "claude-sonnet-5-5",
                      "scout": "claude-haiku-4-5"}
    assert efforts == {"reasoner": "high", "worker": "medium"}


def test_the_model_list_is_the_config_role_model_list_in_order(catalog):
    claude = _backend("claude")
    for role in roles_for(claude):
        assert [i.value for i in model_items(catalog, claude, role)] == [
            m.id for m in compatible_models_for(claude)]


def test_the_model_list_marks_star_budget_and_deprecation(catalog):
    items = {i.value: i for i in model_items(catalog, _backend("claude"), _role("reasoner"))}
    assert "★" in items["claude-opus-5-5"].text
    assert "★" not in items["claude-opus-5"].text
    assert items["claude-fable-5-1"].tag == "over budget"
    assert items["claude-opus-4-6"].tag.startswith("deprecated") and items["claude-opus-4-6"].dim


def test_set_model_clears_effort_for_a_model_without_effort_support(catalog):
    models, efforts = {"worker": "claude-sonnet-5-5"}, {"worker": "medium"}
    set_model(catalog, _backend("claude"), _role("worker"), "claude-haiku-4-5", models, efforts)
    assert models == {"worker": "claude-haiku-4-5"} and efforts == {}


def test_set_model_keeps_an_effort_the_new_model_allows(catalog):
    models, efforts = {"worker": "claude-sonnet-5-5"}, {"worker": "medium"}
    set_model(catalog, _backend("claude"), _role("worker"), "claude-opus-5", models, efforts)
    assert efforts == {"worker": "medium"}


def test_set_model_resets_an_effort_the_new_model_rejects(catalog):
    claude = _backend("claude")
    models, efforts = {"worker": "claude-sonnet-5-5"}, {"worker": "minimal"}
    set_model(catalog, claude, _role("worker"), "claude-opus-5", models, efforts)
    assert efforts == {"worker": "medium"}  # worker's typical effort


def _model(model_id, coding, deprecated=False):
    return Model(id=model_id, label=model_id, family="claude", model_class="opus",
                 aliases={"anthropic": model_id}, coding_index=coding, price_in=1.0,
                 deprecated=deprecated)


def test_initial_pick_prefers_a_current_model_over_a_better_deprecated_one():
    from agent_notes.commands.wizard import _default_model_for_role
    role = Role(name="reasoner", label="Reasoner", description="", budget=5.0)
    picked = _default_model_for_role(
        role, [_model("claude-opus-9", 90.0, deprecated=True), _model("claude-opus-8", 80.0)],
        _backend("claude"))
    assert picked.id == "claude-opus-8"


def test_initial_pick_falls_back_to_the_best_deprecated_model():
    from agent_notes.commands.wizard import _default_model_for_role
    role = Role(name="reasoner", label="Reasoner", description="", budget=5.0)
    picked = _default_model_for_role(
        role, [_model("claude-opus-9", 90.0, deprecated=True),
               _model("claude-opus-8", 80.0, deprecated=True)], _backend("claude"))
    assert picked.id == "claude-opus-9"


def test_role_table_cycles_effort_resets_and_changes_model(catalog):
    claude = _backend("claude")
    models, efforts = recommended_choices(catalog, claude)
    values = [i.value for i in model_items(catalog, claude, _role("worker"))]
    to_haiku = values.index("claude-haiku-4-5") - values.index("claude-sonnet-5-5")
    ui = tui_session(RIGHT, "r", RIGHT, DOWN, ENTER, *[DOWN] * to_haiku, ENTER, ESCAPE)
    edit_models(ui, catalog, claude, models, efforts)
    assert efforts["reasoner"] == "xhigh"
    assert models["worker"] == "claude-haiku-4-5" and "worker" not in efforts
    assert any("Worker · Claude Code · budget $2/M in" in "\n".join(f) for f in ui.term.frames)
