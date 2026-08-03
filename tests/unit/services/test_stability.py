import os
import pytest
from agent_notes.services.stability import (
    STABILITY_STABLE, STABILITY_WIP,
    normalize_stability, enabled_wip, is_visible,
)


def test_normalize_defaults_to_stable():
    assert normalize_stability(None) == STABILITY_STABLE
    assert normalize_stability("") == STABILITY_STABLE
    assert normalize_stability("stable") == STABILITY_STABLE
    assert normalize_stability(" WIP ") == STABILITY_WIP


def test_normalize_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_stability("beta")


def test_enabled_wip_parses_env(monkeypatch):
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", " gemini , notion ,")
    assert enabled_wip() == frozenset({"gemini", "notion"})
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    assert enabled_wip() == frozenset()


def test_is_visible_rules(monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    assert is_visible(STABILITY_STABLE, "claude") is True
    assert is_visible(STABILITY_WIP, "gemini") is False
    assert is_visible(STABILITY_WIP, "gemini", frozenset({"gemini"})) is True
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "gemini")
    assert is_visible(STABILITY_WIP, "gemini") is True
