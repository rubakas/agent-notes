"""Tests that pricing.yaml agrees with the catalog seed.

There are two independent price sources: ``seed.json`` (machine-refreshed, gates
role-budget model selection) and ``pricing.yaml`` (hand-maintained, gates cost
reporting). Nothing reconciles them, so pricing.yaml has historically drifted
behind the seed. These tests fail on any divergence.
"""
import json
import re

import pytest

from agent_notes.config import DATA_DIR
from agent_notes.cost import _pricing
from agent_notes.registries.catalog_loader import _normalize_openai_id

# Vendor prefix used by github-copilot aliases in opencode session logs.
ALIAS_PREFIX = "github-copilot"


def _seed_models() -> list:
    """Yield (provider, seed_id, price_in, price_out) for every catalog model."""
    seed = json.loads((DATA_DIR / "catalog" / "seed.json").read_text())
    return [
        (provider, entry["id"], entry.get("price_in"), entry.get("price_out"))
        for provider, entries in seed.get("providers", {}).items()
        for entry in entries
    ]


def _dotted_version(model_id: str) -> str:
    """'claude-opus-4-8' -> 'claude-opus-4.8' — the github-copilot alias form."""
    return re.sub(r"-(\d+)-(\d+)$", r"-\1.\2", model_id)


def _billed_ids(provider: str, seed_id: str) -> list:
    """Every id form that can reach get_price for this model.

    Three things vary independently and all three reach get_price:
      - separator: OpenAI seed ids are dotted (gpt-5.4-mini) but the registry
        normalizes them to a dash form (gpt-5-4-mini); Anthropic is the reverse,
        dashed ids with dotted github-copilot aliases (claude-opus-4.8).
      - prefix: _opencode_backend passes the logged model string straight
        through, so vendor-prefixed aliases (github-copilot/...) arrive as-is.
        Every glob therefore needs a leading `*`; the o-series globs were the
        only ones in the file that lacked one, and nothing caught it.
    """
    if provider == "openai":
        bare = {seed_id, _normalize_openai_id(seed_id)}
    else:
        bare = {seed_id, _dotted_version(seed_id)}
    return sorted(bare | {f"{ALIAS_PREFIX}/{i}" for i in bare})


SEED_MODELS = _seed_models()


@pytest.mark.parametrize(
    "provider,seed_id,price_in,price_out",
    SEED_MODELS,
    ids=[f"{p}/{i}" for p, i, _, _ in SEED_MODELS],
)
def test_pricing_yaml_matches_seed(provider, seed_id, price_in, price_out, capsys):
    if price_in is None or price_out is None:
        # Deprecated/unrated entries carry no seed price, so there is nothing to
        # reconcile against — pricing.yaml is the only source for them.
        pytest.skip(f"{seed_id} has no seed price")

    for model_id in _billed_ids(provider, seed_id):
        price = _pricing.get_price(model_id)
        # get_price warns and falls back to Sonnet rates when nothing matches.
        # Without this check a missing entry would pass silently for any model
        # that happens to be priced like Sonnet.
        assert "no pricing entry" not in capsys.readouterr().err, (
            f"{model_id} has no pricing.yaml entry and fell back to Sonnet rates"
        )
        assert price["in"] == price_in, (
            f"{model_id}: pricing.yaml bills ${price['in']}/MTok input, "
            f"seed.json says ${price_in}"
        )
        assert price["out"] == price_out, (
            f"{model_id}: pricing.yaml bills ${price['out']}/MTok output, "
            f"seed.json says ${price_out}"
        )
