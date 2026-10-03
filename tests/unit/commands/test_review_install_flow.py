"""The install flow around the review screen (spec 005 FR-001, FR-005, FR-026):
build before confirm, restore on decline, and the collected values reach build,
plan and _execute_install unchanged."""
import inspect
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_notes.commands.wizard import orchestrator
from agent_notes.commands.wizard.review import InstallChoices, initial_choices
from agent_notes.commands.wizard.role_models import Catalog, recommended_choices
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT, SPACE
from agent_notes.services.tui.session import LineSession
from tests.unit.tui.fakes import FakeLineInput, tui_session


class _Calls(list):
    plan = None

    def kinds(self):
        return [kind for kind, _ in self]

    def of(self, kind):
        return [kwargs for k, kwargs in self if k == kind]


@pytest.fixture
def calls(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))  # never the real state.json
    log = _Calls()
    log.plan = SimpleNamespace(to_install=["a", "b", "c"], overwrites=[])

    def fake_plan_install(**kwargs):
        log.append(("plan", kwargs))
        return "manifest"

    real_build, real_execute = orchestrator.build, orchestrator._execute_install

    def fake_build(**kw):
        inspect.signature(real_build).bind(**kw)
        log.append(("build", kw))

    def fake_execute(**kw):
        inspect.signature(real_execute).bind(**kw)
        log.append(("execute", kw))

    monkeypatch.setattr(orchestrator, "build", fake_build)
    monkeypatch.setattr(orchestrator, "_execute_install", fake_execute)
    monkeypatch.setattr("agent_notes.services.installer.plan_install", fake_plan_install)
    monkeypatch.setattr("agent_notes.services.installer.summarize_plan", lambda manifest: log.plan)
    return log


def _run(*keys, session=None):
    ui = session or tui_session(*keys)
    orchestrator._interactive_install(session_factory=lambda: ui)
    return ui


def test_two_keypresses_install_the_recommended_setup(calls):
    _run("i", ENTER)
    assert calls.kinds() == ["build", "plan", "execute"]
    run = calls.of("execute")[0]
    assert (run["clis"], run["scope"], run["copy_mode"]) == ({"claude"}, "global", False)
    models, efforts = recommended_choices(Catalog(), load_registry().get("claude"))
    assert (run["role_models"]["claude"], run["role_efforts"]["claude"]) == (models, efforts)
    assert (run["memory_backend"], run["memory_path"], run["memory_strategy"]) == (
        "local", "", "single-brain")
    assert (run["profile_label"], run["folder_overrides"], run["global_home_override"]) == (
        "", None, "")
    assert run["enabled_plugins"] == {"cost-report": False}
    expected = initial_choices(Catalog(), load_registry()).skills
    assert expected and run["selected_skills"] == expected


def test_the_build_gets_the_selections_before_confirming(calls):
    _run("i", ENTER)
    build, run = calls.of("build")[0], calls.of("execute")[0]
    assert build["role_models"] == run["role_models"]
    assert build["role_efforts"] == run["role_efforts"]
    assert (build["scope"], build["project_path"], build["profile_label"]) == ("global", None, "")


def test_local_scope_builds_for_the_current_folder(calls):
    _run(DOWN, DOWN, RIGHT, "i", ENTER)  # CLIs → Models → Scope, then local
    assert calls.of("build")[0]["project_path"] == Path.cwd()
    assert calls.of("execute")[0]["scope"] == "local"


def test_declining_restores_the_persisted_render_and_installs_nothing(calls, capsys):
    _run("i", ESCAPE, "q")
    assert calls.kinds() == ["build", "plan", "build"]
    restore = calls.of("build")[1]
    assert "role_models" not in restore and "role_efforts" not in restore
    assert "Installation cancelled." in capsys.readouterr().out


def test_q_at_the_confirmation_restores_and_quits(calls, capsys):
    ui = _run("i", "q")
    assert calls.kinds() == ["build", "plan", "build"]
    assert "role_models" not in calls.of("build")[1]
    assert "q quit" in ui.term.text()
    assert "Installation cancelled." in capsys.readouterr().out


def test_q_at_the_confirmation_stays_when_the_restore_fails(calls, monkeypatch, capsys):
    def build_failing_on_restore(**kwargs):
        calls.append(("build", kwargs))
        if "role_models" not in kwargs:
            raise RuntimeError("locked")

    monkeypatch.setattr(orchestrator, "build", build_failing_on_restore)
    ui = _run("i", "q", "q")   # the second q quits from the form
    assert "Restore failed — run agent-notes regenerate: locked" in ui.term.text()
    assert "execute" not in calls.kinds()
    assert "Installation cancelled." in capsys.readouterr().out


def test_the_restore_keeps_scope_and_profile(calls, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    orchestrator._render(InstallChoices(scope="local", profile_label="work"), with_selections=False)
    restore = calls.of("build")[0]
    assert restore["scope"] == "local" and restore["profile_label"] == "work"
    assert Path(restore["project_path"]).resolve() == tmp_path.resolve()


def test_a_failed_build_restores_shows_why_and_never_confirms(calls, monkeypatch):
    def failing_build(**kwargs):
        calls.append(("build", kwargs))
        if "role_models" in kwargs:
            raise RuntimeError("disk full")

    monkeypatch.setattr(orchestrator, "build", failing_build)
    ui = _run("i", "q")
    assert calls.kinds() == ["build", "build"]
    assert "Build failed — disk full" in ui.term.text()


def test_no_cli_selected_refuses_to_build(calls):
    ui = _run(ENTER, SPACE, ENTER, "i", "q")
    assert calls.kinds() == []
    assert "select at least one CLI" in ui.term.text()


def test_plan_gets_the_skills_verbatim_and_the_profile_overrides(calls):
    orchestrator._plan_summary(InstallChoices(clis={"claude"}, skills=[], profile_label="work"),
                               load_registry())
    plan = calls.of("plan")[0]
    assert plan["selected_skills"] == []
    assert plan["folder_overrides"] == {"claude": ".claude-work"}
    assert plan["global_home_override"] == "~/.claude-work"


def test_no_profile_passes_no_overrides(calls):
    orchestrator._plan_summary(InstallChoices(clis={"claude"}), load_registry())
    plan = calls.of("plan")[0]
    assert plan["folder_overrides"] is None and plan["global_home_override"] is None


def test_the_question_counts_files_and_lists_at_most_five_backups(calls):
    calls.plan.overwrites = [SimpleNamespace(dst=f"/x/{i}.md", backup_path=f"/x/{i}.md.bak")
                             for i in range(7)]
    question, lines = orchestrator._plan_summary(InstallChoices(clis={"claude"}), load_registry())
    assert question == "Install 3 files (7 backed up)?"
    assert lines[0] == "backup  /x/0.md  →  /x/0.md.bak"
    assert len(lines) == 6 and lines[-1] == "… 2 more"


def test_no_backup_lines_without_overwrites(calls):
    question, lines = orchestrator._plan_summary(InstallChoices(clis={"claude"}), load_registry())
    assert (question, lines) == ("Install 3 files (0 backed up)?", [])


def test_a_plan_failure_is_logged_and_the_install_can_still_go_ahead(calls, monkeypatch, caplog):
    def broken(**kwargs):
        raise OSError("unreadable")

    monkeypatch.setattr("agent_notes.services.installer.plan_install", broken)
    with caplog.at_level(logging.DEBUG, logger="agent_notes.commands.wizard.orchestrator"):
        question, lines = orchestrator._plan_summary(InstallChoices(clis={"claude"}),
                                                     load_registry())
    assert (question, lines) == ("Install?", [])
    assert "plan_install failed" in caplog.text


def test_without_a_terminal_the_recommended_setup_installs_without_prompts(calls):
    orchestrator._interactive_install(session_factory=lambda: None)
    assert calls.kinds() == ["build", "execute"]


def test_ctrl_c_prints_cancelled(capsys):
    def interrupted():
        raise KeyboardInterrupt

    orchestrator.interactive_install(session_factory=interrupted)
    assert "Cancelled." in capsys.readouterr().out


def test_a_closed_terminal_prints_cancelled(calls, capsys):
    ui = tui_session(EOFError)
    orchestrator.interactive_install(session_factory=lambda: ui)
    assert "Cancelled." in capsys.readouterr().out
    assert calls.kinds() == []


def test_line_mode_installs_with_two_enters(calls, monkeypatch):
    monkeypatch.setattr("agent_notes.services.ui._safe_input", FakeLineInput("", ""))
    _run(session=LineSession())
    assert calls.kinds() == ["build", "plan", "execute"]


def test_line_mode_q_at_the_confirmation_restores_and_quits(calls, monkeypatch, capsys):
    answers = FakeLineInput("", "q")
    monkeypatch.setattr("agent_notes.services.ui._safe_input", answers)
    _run(session=LineSession())
    assert calls.kinds() == ["build", "plan", "build"]
    assert "role_models" not in calls.of("build")[1]
    assert answers.prompts[-1].endswith("[Y/n/q]: ")
    assert "Installation cancelled." in capsys.readouterr().out


def test_a_failed_restore_is_reported(calls, monkeypatch):
    def build_failing_on_restore(**kwargs):
        calls.append(("build", kwargs))
        if "role_models" not in kwargs:
            raise RuntimeError("locked")

    monkeypatch.setattr(orchestrator, "build", build_failing_on_restore)
    ui = _run("i", ESCAPE, "q")
    assert "Restore failed — run agent-notes regenerate: locked" in ui.term.text()


LONG_ERROR = "permission denied while writing " + "/very/long/path" * 8


def test_a_long_restore_error_keeps_the_instruction_on_screen(calls, monkeypatch):
    def build_failing_on_restore(**kwargs):
        calls.append(("build", kwargs))
        if "role_models" not in kwargs:
            raise RuntimeError(LONG_ERROR)

    monkeypatch.setattr(orchestrator, "build", build_failing_on_restore)
    ui = _run("i", ESCAPE, "q")
    footers = [frame[-1] for frame in ui.term.frames]
    assert any(footer.startswith(" Restore failed — run agent-notes regenerate: ")
               for footer in footers)


def test_a_failed_build_and_restore_lead_with_the_instruction(calls, monkeypatch):
    def build_always_failing(**kwargs):
        calls.append(("build", kwargs))
        raise RuntimeError(LONG_ERROR)

    monkeypatch.setattr(orchestrator, "build", build_always_failing)
    ui = _run("i", "q")
    footers = [frame[-1] for frame in ui.term.frames]
    assert any(footer.startswith(" Build and restore failed — run agent-notes regenerate: ")
               for footer in footers)


def test_ctrl_c_at_confirm_restores_then_cancels(calls, capsys):
    ui = tui_session("i", KeyboardInterrupt)
    orchestrator.interactive_install(session_factory=lambda: ui)
    assert calls.kinds() == ["build", "plan", "build"]
    assert "role_models" not in calls.of("build")[1]
    assert "Cancelled." in capsys.readouterr().out


def test_ctrl_c_during_the_build_restores_then_cancels(calls, monkeypatch, capsys):
    def interrupted_build(**kwargs):
        calls.append(("build", kwargs))
        if "role_models" in kwargs:
            raise KeyboardInterrupt

    monkeypatch.setattr(orchestrator, "build", interrupted_build)
    orchestrator.interactive_install(session_factory=lambda: tui_session("i"))
    assert calls.kinds() == ["build", "build"]
    assert "role_models" not in calls.of("build")[1]
    assert "Cancelled." in capsys.readouterr().out


def test_line_mode_ctrl_c_at_the_question_restores_then_exits(calls, monkeypatch):
    answers = iter(["", SystemExit(0)])   # enter = install, then Ctrl-C at "Install …?"

    def line_input(prompt, default=""):
        answer = next(answers)
        if isinstance(answer, BaseException):
            raise answer   # what _safe_input does on Ctrl-C / Ctrl-D
        return answer or default

    monkeypatch.setattr("agent_notes.services.ui._safe_input", line_input)
    with pytest.raises(SystemExit):
        _run(session=LineSession())
    assert calls.kinds() == ["build", "plan", "build"]
    assert "role_models" not in calls.of("build")[1]


def test_a_failed_local_restore_names_this_installs_regenerate_command(calls, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def build_failing_on_restore(**kwargs):
        if "role_models" not in kwargs:
            raise RuntimeError("locked")

    monkeypatch.setattr(orchestrator, "build", build_failing_on_restore)
    catalog, registry = Catalog(), load_registry()
    choices = initial_choices(catalog, registry)
    choices.scope, choices.profile_label = "local", "work"
    ui = tui_session("i", ESCAPE, "q", width=300)
    orchestrator._review(ui, choices, catalog, registry)
    here = Path.cwd()
    assert (f"Restore failed — run cd {here} && agent-notes regenerate --local --profile=work: locked"
            in ui.term.text())
