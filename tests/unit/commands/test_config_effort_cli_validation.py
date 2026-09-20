"""Tests for agent_notes.commands.config._check_effort_valid — the CLI-level
narrowing of a provider-valid effort.

The provider vocabulary says what the API accepts; a CLI backend can accept a
strict subset of it (Codex's `model_reasoning_effort` rejects 'none', which the
OpenAI API allows). Accepting such a value at config time prints SUCCESS for a
setting that render-time silently drops.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_notes.commands.config import _check_effort_valid
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.domain.model import Model
from agent_notes.domain.state import ScopeState, BackendState


ROLE = "worker"
MODEL_ID = "gpt-test"


def _scope_state(cli_name="codex"):
    return ScopeState(clis={cli_name: BackendState(role_models={ROLE: MODEL_ID})})


@pytest.fixture(autouse=True)
def openai_model(monkeypatch):
    """Pin the role's model so the test does not depend on catalog contents."""
    model = Model(id=MODEL_ID, label=MODEL_ID, family="gpt", model_class="gpt",
                  aliases={"openai": MODEL_ID})

    class FakeModelRegistry:
        def get(self, model_id):
            if model_id != MODEL_ID:
                raise KeyError(model_id)
            return model

    monkeypatch.setattr(
        "agent_notes.registries.model_registry.load_model_registry",
        lambda: FakeModelRegistry(),
    )


def _patch_backend(monkeypatch, efforts):
    backend = CLIBackend(
        name="codex",
        label="Codex CLI",
        global_home=Path("/tmp"),
        local_dir=".codex",
        layout={},
        features={"agents": True, "frontmatter": "codex"},
        global_template=None,
        accepted_providers=("openai",),
        efforts=efforts,
    )

    class FakeCLIRegistry:
        def get(self, name):
            if name != backend.name:
                raise KeyError(name)
            return backend

    monkeypatch.setattr(
        "agent_notes.registries.cli_registry.load_registry",
        lambda: FakeCLIRegistry(),
    )


class TestCheckEffortValidCLINarrowing:
    def test_rejects_provider_valid_effort_the_cli_does_not_accept(self, capsys):
        """'none' is in openai.yaml's efforts but not in codex.yaml's — the CLI
        would drop it at render time, so config must not report success."""
        assert _check_effort_valid(_scope_state(), "codex", ROLE, "none") is False

    def test_error_message_names_the_cli_and_its_accepted_efforts(self, capsys):
        _check_effort_valid(_scope_state(), "codex", ROLE, "none")
        out = capsys.readouterr().out
        assert "codex" in out
        for effort in ("minimal", "low", "medium", "high", "xhigh"):
            assert effort in out

    def test_accepts_effort_valid_for_both_provider_and_cli(self):
        assert _check_effort_valid(_scope_state(), "codex", ROLE, "high") is True

    def test_backend_without_declared_efforts_adds_no_constraint(self, monkeypatch):
        _patch_backend(monkeypatch, efforts=())
        assert _check_effort_valid(_scope_state(), "codex", ROLE, "none") is True

    def test_still_rejects_values_the_provider_itself_rejects(self, monkeypatch, capsys):
        _patch_backend(monkeypatch, efforts=())
        assert _check_effort_valid(_scope_state(), "codex", ROLE, "bogus") is False
        assert "openai" in capsys.readouterr().out
