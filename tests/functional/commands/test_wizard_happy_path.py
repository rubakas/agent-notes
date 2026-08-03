"""Integration test: wizard happy-path — full orchestrator flow.

Drives _interactive_install through all 9 steps by mocking the user-input
(prompt/selection) functions to return deterministic choices.  The actual file
placement (_execute_install) is mocked so the test stays fast and isolated from
dist content; the assertion is that _execute_install is called with the exact
aggregated choices the wizard collected.

Choices used:
  CLIs          = {"claude"}
  role_models   = whatever the real _select_models_per_role would produce for claude
                  (we let it run but mock the radio selector to pick the first option)
  scope         = "global"
  copy_mode     = False   (symlink)
  profile       = no profile  (label="", overrides={}, home_override="")
  skills        = a subset: ["git", "obsidian-memory"] (via checkbox fallback)
  memory        = ("local", "")
  cost_report   = False
  confirm       = True
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock, call


class TestWizardHappyPath:
    def test_interactive_install_calls_execute_with_correct_choices(self, monkeypatch):
        """_interactive_install collects choices and passes them verbatim to _execute_install."""

        # ── Non-interactive UI ────────────────────────────────────────────────
        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)

        def _noop(*a, **kw):
            pass

        monkeypatch.setattr("agent_notes.services.ui._clear_screen", _noop)
        monkeypatch.setattr("agent_notes.services.ui._render_step_header", _noop)
        monkeypatch.setattr("agent_notes.commands.wizard._clear_screen", _noop, raising=False)

        # ── Step 1: CLI selection → {"claude"} ──────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            lambda title, options, defaults=None, **kw: {"claude"},
        )

        # ── Step 2: Role/model selection — gate answers "no" so per-role fallback runs ──
        monkeypatch.setattr(
            "agent_notes.commands.wizard._select_accept_all_models",
            lambda **kw: False,
        )
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: options[default][1],
        )
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select",
            lambda title, options, default=0, **kw: options[default][1],
        )

        # ── Step 5: Profile → no profile ─────────────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._select_profile",
            lambda **kw: ("", {}, ""),
        )

        # ── Step 6: Skills — patch _get_skill_groups to return minimal set ────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._get_skill_groups",
            lambda: {"process": ["obsidian-memory"], "Git": ["git"]},
        )
        # checkbox fallback already returns {"claude"} — we need skills to return
        # {"git"} for domain skills.  We'll replace the fallback with one that
        # distinguishes by whether "claude" appears in the options.
        def _smart_checkbox(title, options, defaults=None, **kw):
            # CLI step calls this first (options contain cli names like "claude")
            # Skills step calls this second (options contain skill labels)
            values = {v for _, v in options} if options else set()
            if "claude" in values:
                return {"claude"}
            # domain skills step
            return {"git"}

        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            _smart_checkbox,
        )

        # ── Step 7: Memory backend → local ───────────────────────────────────
        # _select_memory calls _radio_select_fallback; "local" is options[0][1]
        # Already patched above to return options[0][1].

        # ── Step 8: cost_report → False ──────────────────────────────────────
        # _select_cost_report uses radio; first option should be enabled=True,
        # but we'll patch the whole function to return False. The toggle runner
        # (capabilities.py) imports _select_cost_report at module load time, so
        # the patch must target the capabilities module's binding.
        monkeypatch.setattr(
            "agent_notes.commands.wizard.capabilities._select_cost_report",
            lambda **kw: False,
            raising=False,
        )

        # ── Step 9: Confirm → True ────────────────────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._confirm_install",
            lambda *a, **kw: True,
        )

        # ── Suppress build() ─────────────────────────────────────────────────
        with patch("agent_notes.commands.wizard.orchestrator.build"):
            # ── Mock _execute_install and capture call args ──────────────────
            execute_mock = MagicMock()

            with patch(
                "agent_notes.commands.wizard.orchestrator._execute_install",
                execute_mock,
            ), patch(
                "agent_notes.commands.wizard.capabilities._select_cost_report",
                return_value=False,
            ):
                from agent_notes.commands.wizard.orchestrator import _interactive_install
                _interactive_install()

        # ── Assert _execute_install was called ────────────────────────────────
        assert execute_mock.called, "_execute_install must be called by the orchestrator"

        _, kwargs = execute_mock.call_args

        # CLIs
        assert "claude" in kwargs["clis"], \
            f"expected 'claude' in clis, got {kwargs['clis']}"

        # Scope
        assert kwargs["scope"] == "global", \
            f"expected scope='global', got {kwargs['scope']!r}"

        # Copy mode (symlink → False)
        assert kwargs["copy_mode"] is False, \
            f"expected copy_mode=False (symlink), got {kwargs['copy_mode']!r}"

        # Memory backend
        assert kwargs["memory_backend"] == "local", \
            f"expected memory_backend='local', got {kwargs['memory_backend']!r}"

        # Cost report
        assert kwargs["enabled_plugins"]["cost-report"] is False, \
            f"expected enabled_plugins['cost-report']=False, got {kwargs['enabled_plugins']!r}"

        # Profile: no label, no overrides
        assert kwargs.get("profile_label", "") == "", \
            f"expected empty profile_label, got {kwargs.get('profile_label')!r}"

        # role_models: must be a dict keyed at minimum by "claude"
        assert isinstance(kwargs.get("role_models"), dict), \
            "role_models must be a dict"
        assert "claude" in kwargs["role_models"], \
            f"role_models must have 'claude' key, got {list(kwargs['role_models'].keys())}"

        # selected_skills: must be a list containing at least "obsidian-memory" (process) and "git"
        selected = kwargs.get("selected_skills", [])
        assert isinstance(selected, list), "selected_skills must be a list"
        assert "obsidian-memory" in selected, \
            f"process skill 'obsidian-memory' must always be included, got {selected}"
        assert "git" in selected, \
            f"selected domain skill 'git' must be included, got {selected}"

    def test_accept_all_yes_skips_per_role_prompts_in_full_flow(self, monkeypatch):
        """When accept_all=True the per-role _radio_select prompts are never invoked."""

        # ── Non-interactive UI ────────────────────────────────────────────────
        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)

        def _noop(*a, **kw):
            pass

        monkeypatch.setattr("agent_notes.services.ui._clear_screen", _noop)
        monkeypatch.setattr("agent_notes.services.ui._render_step_header", _noop)
        monkeypatch.setattr("agent_notes.commands.wizard._clear_screen", _noop, raising=False)

        # ── Step 1: CLI selection → {"claude"} ──────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            lambda title, options, defaults=None, **kw: {"claude"},
        )

        # ── Step 2: accept_all=True — per-role radio must NOT fire ───────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._select_accept_all_models",
            lambda **kw: True,
        )
        per_role_calls = []

        def _radio_guard(title, options, default=0, **kw):
            # any call that touches a "Role" line is a per-role model prompt
            if any("Role" in ln for ln in title.splitlines()):
                per_role_calls.append(title)
                raise AssertionError(f"per-role radio should not run when accept-all=yes: {title!r}")
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", _radio_guard)
        monkeypatch.setattr("agent_notes.commands.wizard._radio_select", _radio_guard)

        # ── Step 5: Profile → no profile ─────────────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._select_profile",
            lambda **kw: ("", {}, ""),
        )

        # ── Step 6: Skills ────────────────────────────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._get_skill_groups",
            lambda: {"process": ["obsidian-memory"], "Git": ["git"]},
        )

        def _smart_checkbox(title, options, defaults=None, **kw):
            values = {v for _, v in options} if options else set()
            if "claude" in values:
                return {"claude"}
            return {"git"}

        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            _smart_checkbox,
        )

        # ── Step 8: cost_report → False ──────────────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard.capabilities._select_cost_report",
            lambda **kw: False,
            raising=False,
        )

        # ── Step 9: Confirm → True ────────────────────────────────────────────
        monkeypatch.setattr(
            "agent_notes.commands.wizard._confirm_install",
            lambda *a, **kw: True,
        )

        with patch("agent_notes.commands.wizard.orchestrator.build"):
            execute_mock = MagicMock()
            with patch(
                "agent_notes.commands.wizard.orchestrator._execute_install",
                execute_mock,
            ), patch(
                "agent_notes.commands.wizard.capabilities._select_cost_report",
                return_value=False,
            ):
                from agent_notes.commands.wizard.orchestrator import _interactive_install
                _interactive_install()

        assert execute_mock.called, "_execute_install must be called"
        _, kwargs = execute_mock.call_args
        assert "claude" in kwargs["role_models"], \
            f"accept-all must populate role_models, got {list(kwargs['role_models'].keys())}"
        assert per_role_calls == [], \
            f"per-role radio was invoked: {per_role_calls}"
