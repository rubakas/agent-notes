"""Equivalence gate: the generated catalog must reproduce the 14 hand-written models exactly.

Expected values are derived from the 14 YAML files and hardcoded here so the test
remains valid after those files are deleted.  Run this test GREEN before deleting
agent_notes/data/models/*.yaml.
"""

from __future__ import annotations

import pytest

from agent_notes.registries.model_registry import load_model_registry


# ---------------------------------------------------------------------------
# Ground truth — derived verbatim from the 14 hand-written YAML files.
# ---------------------------------------------------------------------------
EXPECTED = [
    {
        "id": "claude-fable-5",
        "label": "Claude Fable 5",
        "family": "claude",
        "model_class": "fable",
        "aliases": {"anthropic": "claude-fable-5"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": False,
        "never_default": True,
    },
    {
        "id": "claude-haiku-4-5",
        "label": "Claude Haiku 4.5",
        "family": "claude",
        "model_class": "haiku",
        "aliases": {"anthropic": "claude-haiku-4-5"},
        "capabilities": {"vision": True, "long_context": False, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
    {
        "id": "claude-opus-4-1",
        "label": "Claude Opus 4.1",
        "family": "claude",
        "model_class": "opus",
        "aliases": {"anthropic": "claude-opus-4-1"},
        "capabilities": {"vision": True, "long_context": False, "tool_use": True},
        "deprecated": True,
        "never_default": False,
    },
    {
        "id": "claude-opus-4-5",
        "label": "Claude Opus 4.5",
        "family": "claude",
        "model_class": "opus",
        "aliases": {"anthropic": "claude-opus-4-5"},
        "capabilities": {"vision": True, "long_context": False, "tool_use": True},
        "deprecated": True,
        "never_default": False,
    },
    {
        "id": "claude-opus-4-6",
        "label": "Claude Opus 4.6",
        "family": "claude",
        "model_class": "opus",
        "aliases": {"anthropic": "claude-opus-4-6"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": True,
        "never_default": False,
    },
    {
        "id": "claude-opus-4-7",
        "label": "Claude Opus 4.7",
        "family": "claude",
        "model_class": "opus",
        "aliases": {"anthropic": "claude-opus-4-7"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": True,
        "never_default": False,
    },
    {
        "id": "claude-opus-4-8",
        "label": "Claude Opus 4.8",
        "family": "claude",
        "model_class": "opus",
        "aliases": {"anthropic": "claude-opus-4-8"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
    {
        "id": "claude-sonnet-4",
        "label": "Claude Sonnet 4",
        "family": "claude",
        "model_class": "sonnet",
        "aliases": {"anthropic": "claude-sonnet-4-20250514"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": True,
        "never_default": False,
    },
    {
        "id": "claude-sonnet-4-5",
        "label": "Claude Sonnet 4.5",
        "family": "claude",
        "model_class": "sonnet",
        "aliases": {"anthropic": "claude-sonnet-4-5"},
        "capabilities": {"vision": True, "long_context": False, "tool_use": True},
        "deprecated": True,
        "never_default": False,
    },
    {
        "id": "claude-sonnet-4-6",
        "label": "Claude Sonnet 4.6",
        "family": "claude",
        "model_class": "sonnet",
        "aliases": {"anthropic": "claude-sonnet-4-6"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
    {
        "id": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "family": "claude",
        "model_class": "sonnet",
        "aliases": {"anthropic": "claude-sonnet-5"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
    {
        "id": "gpt-5-4",
        "label": "GPT-5.4",
        "family": "gpt",
        "model_class": "sonnet",
        "aliases": {"openai": "gpt-5.4"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
    {
        "id": "gpt-5-4-mini",
        "label": "GPT-5.4 Mini",
        "family": "gpt",
        "model_class": "haiku",
        "aliases": {"openai": "gpt-5.4-mini"},
        "capabilities": {"vision": True, "long_context": False, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
    {
        "id": "gpt-5-5",
        "label": "GPT-5.5",
        "family": "gpt",
        "model_class": "opus",
        "aliases": {"openai": "gpt-5.5"},
        "capabilities": {"vision": True, "long_context": True, "tool_use": True},
        "deprecated": False,
        "never_default": False,
    },
]

EXPECTED_BY_ID = {e["id"]: e for e in EXPECTED}
FIELDS = ("id", "label", "family", "model_class", "aliases", "capabilities", "deprecated", "never_default")


def test_catalog_has_exactly_14_models():
    """Catalog must contain exactly the 14 expected models — no more, no less."""
    registry = load_model_registry()
    ids = set(registry.ids())
    expected_ids = set(EXPECTED_BY_ID.keys())
    assert ids == expected_ids, (
        f"ID mismatch.\n"
        f"  Only in catalog:  {sorted(ids - expected_ids)}\n"
        f"  Missing from catalog: {sorted(expected_ids - ids)}"
    )


@pytest.mark.parametrize("expected", EXPECTED, ids=[e["id"] for e in EXPECTED])
def test_catalog_model_matches_expected(expected):
    """Each generated model must match the hand-written YAML field for field."""
    registry = load_model_registry()
    model = registry.get(expected["id"])
    for field in FIELDS:
        actual = getattr(model, field)
        want = expected[field]
        assert actual == want, (
            f"Model '{expected['id']}' field '{field}':\n"
            f"  want: {want!r}\n"
            f"  got:  {actual!r}"
        )
