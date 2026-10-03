"""An install renders from THIS run's choices, and a run nobody confirmed leaves no trace
(spec 007 FR-A03, FR-A04, R4, and the restore on decline for the flags path)."""
import json
from pathlib import Path

import pytest

import agent_notes.commands.build as build_module
import agent_notes.commands.wizard.orchestrator as orchestrator
from agent_notes.commands.install import install
from agent_notes.commands.wizard.review import InstallChoices
from agent_notes.domain.state import MemoryConfig
from agent_notes.services.state_store import load_state
from agent_notes.services.tui.session import LineSession
from tests.functional.commands.cleanup_world import World
from tests.unit.tui.fakes import FakeLineInput

from agent_notes.commands._install_helpers import recommended_pins

PINNED = "claude-haiku-4-5"
RECOMMENDED = recommended_pins()[0]["claude"]["worker"]
assert RECOMMENDED != PINNED


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _coder(world) -> str:
    return (world.dist / "claude" / "agents" / "coder.md").read_text()


def _model(world) -> str:
    return next(line for line in _coder(world).splitlines() if line.startswith("model:"))


def _pin_worker_in_state(world, scope_key, entry):
    """What an earlier install left behind: the worker role pinned to a non-recommended model."""
    state = json.loads(world.state_file.read_text())
    holder = state["global"] if scope_key == "global" else state["local"][str(world.project)]
    holder["clis"]["claude"]["role_models"]["worker"] = PINNED
    world.state_file.write_text(json.dumps(state))


def _choices(**overrides) -> InstallChoices:
    choices = InstallChoices()
    choices.clis = {"claude"}
    choices.role_models = {"claude": {"reasoner": "claude-opus-5-5"}}
    for name, value in overrides.items():
        setattr(choices, name, value)
    return choices


class TestUnmentionedPinsAreNotPreserved:
    def test_the_flags_path_renders_the_recommended_model(self, world):
        world.use("main")
        install(local=True)
        _pin_worker_in_state(world, "local", None)
        build_module.build(scope="local", project_path=world.project)
        assert _model(world) == f"model: {PINNED}"

        install(local=True, assume_yes=True)

        assert _model(world) == f"model: {RECOMMENDED}"

    def test_the_flags_path_records_the_pins_it_used(self, world):
        world.use("main")
        install(local=True)
        _pin_worker_in_state(world, "local", None)

        install(local=True, assume_yes=True)

        pins = load_state().local_installs[str(world.project)].clis["claude"].role_models
        assert pins["worker"] == RECOMMENDED
        assert pins["reasoner"] == "claude-opus-5-5"

    def test_a_model_and_an_effort_pinned_earlier_are_gone_after_a_flags_reinstall(self, world):
        world.use("main")
        install(local=True)
        state = json.loads(world.state_file.read_text())
        claude = state["local"][str(world.project)]["clis"]["claude"]
        claude["role_models"]["worker"], claude["role_efforts"]["worker"] = "claude-opus-5-5", "high"
        world.state_file.write_text(json.dumps(state))
        build_module.build(scope="local", project_path=world.project)
        assert "model: claude-opus-5-5" in _coder(world) and "effort: high" in _coder(world)

        install(local=True, assume_yes=True)

        rendered = _coder(world)
        assert f"model: {RECOMMENDED}" in rendered and "effort: medium" in rendered
        assert "claude-opus-5-5" not in rendered and "effort: high" not in rendered
        saved = load_state().local_installs[str(world.project)].clis["claude"]
        assert (saved.role_models["worker"], saved.role_efforts["worker"]) == (RECOMMENDED, "medium")

    def test_a_pin_the_run_did_not_mention_is_not_preserved_either(self, world, monkeypatch):
        """The recommended pins cover every role today, so only a CLI the run leaves out shows
        whether the render starts from the saved install (fresh=False) or from this run alone."""
        world.use("main")
        install(local=True)
        opencode_coder = world.dist / "opencode" / "agents" / "coder.md"
        default_model = next(l for l in opencode_coder.read_text().splitlines() if l.startswith("model:"))
        state = json.loads(world.state_file.read_text())
        opencode = state["local"][str(world.project)]["clis"]["opencode"]
        opencode["role_models"]["worker"] = "claude-opus-5-5"
        world.state_file.write_text(json.dumps(state))
        build_module.build(scope="local", project_path=world.project)
        assert "model: claude-opus-5-5" in opencode_coder.read_text()
        models, efforts = recommended_pins()
        monkeypatch.setattr("agent_notes.commands.install.recommended_pins",
                            lambda: ({"claude": models["claude"]}, {"claude": efforts["claude"]}))

        install(local=True, assume_yes=True)

        assert default_model in opencode_coder.read_text()
        assert "claude-opus-5-5" not in opencode_coder.read_text()

    def test_the_wizard_render_ignores_the_pins_of_a_cli_this_run_did_not_select(self, world):
        world.use("main")
        world.wizard(clis=("claude", "opencode"),
                     role_models={"claude": {"worker": PINNED}, "opencode": {"worker": PINNED}})
        build_module.build(scope="global")
        opencode_coder = world.dist / "opencode" / "agents" / "coder.md"
        assert PINNED in opencode_coder.read_text()

        assert orchestrator._render(_choices(role_models={"claude": {"worker": RECOMMENDED}}),
                                    with_selections=True) is None

        assert PINNED not in opencode_coder.read_text()
        assert _model(world) == f"model: {RECOMMENDED}"

    def test_regenerate_and_config_saves_still_render_the_install_as_saved(self, world):
        world.use("main")
        world.wizard(role_models={"claude": {"worker": PINNED}})

        build_module.build(scope="global", role_models={"claude": {"reasoner": "claude-opus-5-5"}})

        assert _model(world) == f"model: {PINNED}"


class TestMemoryAndPluginsTakeEffectOnTheFirstInstall:
    def test_obsidian_reaches_the_rendered_agents_and_claude_md(self, world, tmp_path):
        world.use("main")
        vault = tmp_path / "vault"
        choices = _choices(memory=MemoryConfig(backend="obsidian", path=str(vault)))

        assert orchestrator._render(choices, with_selections=True) is None

        assert str(vault) in _coder(world)
        assert str(vault) in (world.dist / "claude" / "CLAUDE.md").read_text()

    def test_a_plugin_switched_on_installs_its_hook_and_allow_entry_at_once(self, world):
        world.use("main")

        world.wizard(plugins={"cost-report": True})

        settings = (world.home / ".claude" / "settings.json").read_text()
        assert "agent-notes cost-report" in settings
        assert "Bash(agent-notes cost-report)" in settings

    def test_a_plugin_switched_off_loses_its_hook_and_allow_entry_in_the_same_install(self, world):
        world.use("main")
        world.wizard(plugins={"cost-report": True})

        world.wizard(plugins={"cost-report": False})

        assert "cost-report" not in (world.home / ".claude" / "settings.json").read_text()

    def test_the_plugin_include_follows_this_runs_toggle_in_the_render(self, world):
        world.use("main")
        include = (world.dist / "claude" / "CLAUDE.md")
        assert orchestrator._render(_choices(plugins={"cost-report": False}), with_selections=True) is None
        without = include.read_text()

        assert orchestrator._render(_choices(plugins={"cost-report": True}), with_selections=True) is None

        assert include.read_text() != without


class TestADeclineChangesNothing:
    def _decline(self, world, monkeypatch, tmp_path):
        monkeypatch.setattr("agent_notes.services.ui._safe_input", FakeLineInput("", "q"))
        real = orchestrator.initial_choices

        def changed(catalog, cli_registry, *a, **k):
            choices = real(catalog, cli_registry, *a, **k)
            choices.memory = MemoryConfig(backend="obsidian", path=str(tmp_path / "vault"))
            choices.plugins = {"cost-report": True}
            choices.role_models["claude"]["worker"] = PINNED
            return choices

        monkeypatch.setattr(orchestrator, "initial_choices", changed)
        orchestrator._interactive_install(session_factory=lambda: LineSession())

    def test_state_config_settings_and_dist_are_byte_identical(self, world, monkeypatch, tmp_path):
        world.use("main")
        world.wizard()
        build_module.build(scope="global")  # dist as the saved install renders it
        user_config = world.paths("main")["xdg"] / "agent-notes" / "config.yaml"
        before = (world.tree(), world.state_file.read_bytes(), world.dist_files(),
                  user_config.read_bytes() if user_config.exists() else None)

        self._decline(world, monkeypatch, tmp_path)

        after = (world.tree(), world.state_file.read_bytes(), world.dist_files(),
                 user_config.read_bytes() if user_config.exists() else None)
        assert after == before


class TestTheFlagsPathRestoresDistWhenItDoesNotPlace:
    @pytest.fixture
    def existing(self, world):
        world.use("main")
        install(local=True)
        _pin_worker_in_state(world, "local", None)
        build_module.build(scope="local", project_path=world.project)
        return world

    def test_a_no_leaves_dist_byte_identical(self, existing, monkeypatch):
        world = existing
        before = world.dist_files()
        monkeypatch.setattr("agent_notes.commands.install.has_terminal", lambda: True)
        monkeypatch.setattr("agent_notes.services.ui._safe_input", lambda prompt, default="": "n")

        install(local=True)

        assert world.dist_files() == before
        assert _model(world) == f"model: {PINNED}"

    def test_an_error_before_placing_leaves_dist_byte_identical(self, existing, monkeypatch):
        world = existing
        before = world.dist_files()
        monkeypatch.setattr("agent_notes.commands.install._confirm_replace",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("plan failed")))

        with pytest.raises(RuntimeError, match="plan failed"):
            _install_with_tty(monkeypatch)

        assert world.dist_files() == before


def _install_with_tty(monkeypatch):
    monkeypatch.setattr("agent_notes.commands.install.has_terminal", lambda: True)
    install(local=True)
