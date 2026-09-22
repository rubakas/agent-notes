"""Effort emission is gated on the MODEL, not only on the provider.

Claude Haiku 4.5 accepts no reasoning-effort setting (absent from the supported
models on platform.claude.com/docs/en/build-with-claude/effort; the models
overview reads "Default effort: Not supported"), yet three shipped agents both
declare `effort: low` and resolve to it. The declaration is fine — it becomes
meaningful if those agents ever resolve elsewhere — so only the EMISSION is
gated, via the `effort_support` capability.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_notes.data.templates.frontmatter import claude as claude_template
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.domain.model import Model
from agent_notes.domain.provider import Provider
from agent_notes.domain.role import Role
from agent_notes.registries.model_registry import ModelRegistry
from agent_notes.registries.provider_registry import ProviderRegistry
from agent_notes.services.rendering import _resolve_effort


HAIKU = Model(
    id="claude-haiku-4-5", label="Claude Haiku 4.5", family="claude",
    model_class="haiku", aliases={"anthropic": "claude-haiku-4-5"},
    capabilities={"effort_support": False},
)
SONNET = Model(
    id="claude-sonnet-5", label="Claude Sonnet 5", family="claude",
    model_class="sonnet", aliases={"anthropic": "claude-sonnet-5"},
    capabilities={"effort_support": True},
)
ANTHROPIC = Provider(
    name="anthropic", efforts=("low", "medium", "high", "xhigh", "max"),
    default_effort="high",
)

CLAUDE_BACKEND = CLIBackend(
    name="claude", label="Claude Code", global_home=Path("/tmp"), local_dir=".claude",
    layout={}, features={"agents": True, "frontmatter": "claude"}, global_template=None,
    accepted_providers=("anthropic",), use_model_class=False, preferred_family="claude",
)

AGENT_CONFIG = {
    "description": "Fast file discovery",
    "role": "scout",
    "color": "cyan",
    "effort": "low",
}


@pytest.fixture(autouse=True)
def _registries(monkeypatch):
    role = Role(name="scout", label="Scout", description="", typical_effort="low")

    class FakeRoleRegistry:
        def get(self, name):
            if name != "scout":
                raise KeyError(name)
            return role

    monkeypatch.setattr(
        "agent_notes.registries.role_registry.default_role_registry",
        lambda: FakeRoleRegistry(),
    )
    monkeypatch.setattr(
        "agent_notes.registries.provider_registry.default_provider_registry",
        lambda: ProviderRegistry([ANTHROPIC]),
    )


def _render(model) -> str:
    registry = ModelRegistry([HAIKU, SONNET])
    resolved_effort = _resolve_effort(
        "explorer", AGENT_CONFIG, CLAUDE_BACKEND, None, {}, model.id, registry
    )
    return claude_template.render({
        "agent_name": "explorer",
        "agent_config": AGENT_CONFIG,
        "model_str": model.id,
        "resolved_effort": resolved_effort,
        "backend_name": "claude",
        "backend": CLAUDE_BACKEND,
    })


class TestEffortSupportGatesEmission:
    def test_no_effort_emitted_for_a_haiku_backed_agent(self):
        frontmatter = _render(HAIKU)
        assert "model: claude-haiku-4-5" in frontmatter
        assert "effort:" not in frontmatter, (
            "claude-haiku-4-5 does not support output_config.effort, so the "
            "rendered agent file must carry no effort field"
        )

    def test_effort_is_emitted_for_a_sonnet_backed_agent(self):
        frontmatter = _render(SONNET)
        assert "model: claude-sonnet-5" in frontmatter
        assert "effort: low" in frontmatter, (
            "gating on effort_support must not suppress effort for models that "
            "do support it"
        )


class TestShippedCatalogMarksHaikuUnsupported:
    def test_claude_haiku_4_5_declares_no_effort_support(self):
        from agent_notes.registries.model_registry import load_model_registry

        model = load_model_registry().get("claude-haiku-4-5")
        assert model.capabilities.get("effort_support") is False
