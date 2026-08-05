"""Equivalence gate: the generated catalog must reproduce the 14 hand-written models exactly.

Expected values are derived from the 14 YAML files and hardcoded here so the test
remains valid after those files are deleted.  Run this test GREEN before deleting
agent_notes/data/models/*.yaml.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest

from agent_notes.registries.catalog_loader import CATALOG_DIR, load_catalog
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


# ---------------------------------------------------------------------------
# Catalog invariant tests — hold for ANY valid catalog, regardless of size.
# ---------------------------------------------------------------------------

def test_no_duplicate_model_ids():
    """No model id may appear more than once in the loaded catalog or raw seed.

    The ModelRegistry constructor silently dedupes via dict comprehension, so a
    raw load_catalog() list is checked first, then the seed.json is inspected
    both within each provider and across providers.
    """
    # Registry-level: load_catalog returns a list; duplicates would be silently
    # swallowed by ModelRegistry.__init__ — detect them before that step.
    models = load_catalog()
    id_counts = Counter(m.id for m in models)
    duplicates = sorted(mid for mid, count in id_counts.items() if count > 1)
    assert not duplicates, (
        f"Duplicate model ids produced by load_catalog(): {duplicates}"
    )

    # Seed-level: inspect the raw JSON so a corrupt seed is also caught.
    seed = json.loads((CATALOG_DIR / "seed.json").read_text())

    all_normalized: list[str] = []
    for provider, entries in seed.get("providers", {}).items():
        provider_ids: list[str] = []
        for entry in entries:
            raw_id: str = entry["id"]
            # Mirror the normalization in catalog_loader._normalize_openai_id
            normalized = raw_id.replace(".", "-") if provider == "openai" else raw_id
            provider_ids.append(normalized)
            all_normalized.append(normalized)

        within_counts = Counter(provider_ids)
        within_dups = sorted(mid for mid, cnt in within_counts.items() if cnt > 1)
        assert not within_dups, (
            f"Duplicate ids within provider '{provider}' in seed.json: {within_dups}"
        )

    cross_counts = Counter(all_normalized)
    cross_dups = sorted(mid for mid, cnt in cross_counts.items() if cnt > 1)
    assert not cross_dups, (
        f"Duplicate ids across providers in seed.json: {cross_dups}"
    )


def test_family_matches_id_prefix():
    """An id starting with 'claude-' must have family='claude'; 'gpt-' must have family='gpt'.

    A mis-applied family rule would silently produce wrong routing at dispatch time.
    """
    registry = load_model_registry()
    violations: list[str] = []
    for model in registry.all():
        if model.id.startswith("claude-") and model.family != "claude":
            violations.append(
                f"'{model.id}' starts with 'claude-' but has family={model.family!r}"
            )
        if model.id.startswith("gpt-") and model.family != "gpt":
            violations.append(
                f"'{model.id}' starts with 'gpt-' but has family={model.family!r}"
            )
    assert not violations, "Family/prefix mismatch:\n  " + "\n  ".join(violations)


def test_alias_provider_matches_family():
    """Claude-family models must not carry an 'openai' alias; gpt-family must not carry 'anthropic'.

    A cross-provider alias would cause a model to be dispatched to the wrong
    provider endpoint at runtime.
    """
    registry = load_model_registry()
    violations: list[str] = []
    for model in registry.all():
        if model.family == "claude" and "openai" in model.aliases:
            violations.append(
                f"'{model.id}' is claude-family but has an 'openai' alias key"
            )
        if model.family == "gpt" and "anthropic" in model.aliases:
            violations.append(
                f"'{model.id}' is gpt-family but has an 'anthropic' alias key"
            )
    assert not violations, "Cross-provider alias violations:\n  " + "\n  ".join(violations)


def test_every_model_has_valid_family_and_class():
    """Every model's family and model_class must be from the known-valid sets.

    These sets mirror the values that the rules.yaml families/classes sections
    can produce. An unrecognised value means a rule was added without updating
    this guard, which warrants an explicit review.
    """
    # Derived from catalog/rules.yaml families and classes sections.
    valid_families = {"claude", "gpt"}
    valid_classes = {"fable", "opus", "sonnet", "haiku"}

    registry = load_model_registry()
    violations: list[str] = []
    for model in registry.all():
        if not model.family or model.family not in valid_families:
            violations.append(
                f"'{model.id}' has invalid family={model.family!r} "
                f"(expected one of {sorted(valid_families)})"
            )
        if not model.model_class or model.model_class not in valid_classes:
            violations.append(
                f"'{model.id}' has invalid model_class={model.model_class!r} "
                f"(expected one of {sorted(valid_classes)})"
            )
    assert not violations, "Invalid family or model_class:\n  " + "\n  ".join(violations)


_ID_PATTERN = re.compile(r"^[a-z0-9.\-]+$")


def test_model_ids_well_formed():
    """Every model id must be non-empty and match ^[a-z0-9.\\-]+$ (lowercase, digits, dot, dash).

    An id with spaces, slashes, uppercase, or control characters would break
    template expansion, file paths, and API calls that embed the id directly.
    """
    registry = load_model_registry()
    violations: list[str] = []
    for model in registry.all():
        if not model.id:
            violations.append("A model has an empty id")
        elif not _ID_PATTERN.match(model.id):
            violations.append(
                f"'{model.id}' does not match ^[a-z0-9.\\-]+$"
            )
    assert not violations, "Malformed model ids:\n  " + "\n  ".join(violations)
