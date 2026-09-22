"""model_class must track capability, not name shape.

The class globs in rules.yaml are matched against the id alone, so a glob that
only fits today's naming can put a cheap, weak model in the most expensive tier
(this is what `gpt-*` -> opus did: 10 of 13 GPT ids classed opus, spanning
coding_index 77.4 down to 37.8 and $10.00 down to $0.05 per 1M input tokens).

Every bound below is DERIVED from the Claude models that name each tier —
Anthropic's own naming is the only authority we have for what "opus", "sonnet"
and "haiku" mean as capability tiers. Nothing here is a hand-picked number
fitted to today's GPT ids, so a catalog refresh moves the bounds with the data
instead of silently widening the band it has to clear. An earlier revision used
literal constants whose premium floor (70.0) sat BELOW its sonnet ceiling
(72.0); the overlap meant the two hardest-to-classify models could be swapped
between tiers with the suite still green.
"""

from __future__ import annotations

import pytest

from agent_notes.registries.catalog_loader import CATALOG_DIR, load_catalog


PREMIUM_CLASSES = ("opus", "fable")


def _seed_models():
    return load_catalog(CATALOG_DIR)


def _claude(model_class) -> list:
    classes = model_class if isinstance(model_class, tuple) else (model_class,)
    return [m for m in _seed_models()
            if m.family == "claude" and m.model_class in classes
            and m.coding_index is not None]


# The weakest Claude model named opus or fable. A model classed premium must be
# at least as capable as the weakest model Anthropic itself calls premium.
PREMIUM_MIN_CODING_INDEX = min(m.coding_index for m in _claude(PREMIUM_CLASSES))

# The strongest Claude model named sonnet. Above it a model is no longer middle
# tier. This sits BELOW the premium floor, so the two bands cannot overlap and
# a model in the gap has to be classified deliberately.
SONNET_MAX_CODING_INDEX = max(m.coding_index for m in _claude("sonnet"))

# The weakest NON-DEPRECATED Claude model named sonnet: the small tier must not
# out-rank the weakest middle-tier model a user can actually select. Deprecated
# sonnets have to be excluded — claude-sonnet-4 is 37.6, below Anthropic's own
# claude-haiku-4-5 at 43.9, so including them would make the ceiling
# self-contradictory rather than merely loose.
HAIKU_MAX_CODING_INDEX = min(
    m.coding_index for m in _claude("sonnet") if not m.deprecated
)

# A premium model must cost strictly more than every small-tier model. Derived
# rather than assumed: this is what rules out the bargain tier, and it is the
# same quantity the price-inversion test below uses.
PREMIUM_MIN_PRICE_IN = max(
    m.price_in for m in _seed_models()
    if m.model_class == "haiku" and m.price_in is not None
)

# Models the catalog carries with no coding_index. They cannot be checked
# against the capability bands, so each is listed here with the reason it is
# acceptable unrated. A refresh that introduces a new unrated model fails until
# someone makes that call — unrated models are the most likely to be
# misclassified, so they must not be skipped silently.
UNRATED_BY_DECISION = {
    "claude-opus-4-1": "deprecated legacy Opus; its tier comes from Anthropic's own name",
    "claude-opus-4-5": "deprecated legacy Opus; its tier comes from Anthropic's own name",
    "claude-opus-4-6": "deprecated legacy Opus; its tier comes from Anthropic's own name",
    "gpt-5-nano": "size suffix puts it in the small tier, the cheapest option available",
    "gpt-5-2": "unrated GPT falls through to the middle tier, the deliberate default in rules.yaml",
}


def test_capability_bands_do_not_overlap():
    """A premium model cannot also satisfy the sonnet ceiling, and vice versa —
    otherwise a boundary misclassification passes in both directions."""
    assert SONNET_MAX_CODING_INDEX < PREMIUM_MIN_CODING_INDEX, (
        f"sonnet ceiling {SONNET_MAX_CODING_INDEX} is not below the premium "
        f"floor {PREMIUM_MIN_CODING_INDEX}: the bands overlap, so a model in "
        "the overlap can be classed either way with the suite still green"
    )
    assert HAIKU_MAX_CODING_INDEX < SONNET_MAX_CODING_INDEX, (
        f"haiku ceiling {HAIKU_MAX_CODING_INDEX} is not below the sonnet "
        f"ceiling {SONNET_MAX_CODING_INDEX}"
    )


@pytest.mark.parametrize("model", _seed_models(), ids=lambda m: m.id)
def test_unrated_models_are_an_explicit_decision(model):
    if model.coding_index is not None:
        return
    assert model.id in UNRATED_BY_DECISION, (
        f"{model.id} has no coding_index, so the capability bands cannot check "
        f"its {model.model_class} class. Add it to UNRATED_BY_DECISION with the "
        "reason its tier is safe unrated, or give the seed a coding_index"
    )


@pytest.mark.parametrize("model", _seed_models(), ids=lambda m: m.id)
def test_class_is_consistent_with_capability_and_price(model):
    if model.model_class in PREMIUM_CLASSES:
        assert model.price_in is not None and model.price_in > PREMIUM_MIN_PRICE_IN, (
            f"{model.id} classes {model.model_class} at ${model.price_in}/M in — "
            f"no more than the ${PREMIUM_MIN_PRICE_IN}/M small tier, so it "
            "cannot be a premium tier"
        )
        if model.coding_index is not None:
            assert model.coding_index >= PREMIUM_MIN_CODING_INDEX, (
                f"{model.id} classes {model.model_class} with coding_index "
                f"{model.coding_index}, below the premium floor "
                f"{PREMIUM_MIN_CODING_INDEX}"
            )
    elif model.model_class == "sonnet" and model.coding_index is not None:
        assert model.coding_index <= SONNET_MAX_CODING_INDEX, (
            f"{model.id} classes sonnet with coding_index {model.coding_index}, "
            f"above the sonnet ceiling {SONNET_MAX_CODING_INDEX} — a frontier "
            "model must not be understated as the middle tier"
        )
    elif model.model_class == "haiku" and model.coding_index is not None:
        assert model.coding_index < HAIKU_MAX_CODING_INDEX, (
            f"{model.id} classes haiku with coding_index {model.coding_index}, "
            f"at or above the haiku ceiling {HAIKU_MAX_CODING_INDEX} — a "
            "capable model must not be understated as the small tier"
        )


def test_premium_tier_does_not_undercut_the_small_tier():
    """Price must not invert across tiers. The old form of this test allowed a
    100x spread inside the premium tier, which was a number chosen to clear the
    75x the catalog happened to have, not a defended bound."""
    premium = [m for m in _seed_models() if m.model_class in PREMIUM_CLASSES]
    prices = [m.price_in for m in premium if m.price_in is not None]
    assert prices, "no premium-classed models found"
    assert min(prices) > PREMIUM_MIN_PRICE_IN, (
        f"the cheapest premium model costs ${min(prices)}/M in, no more than "
        f"the ${PREMIUM_MIN_PRICE_IN}/M small tier: "
        + ", ".join(f"{m.id}=${m.price_in}" for m in premium)
    )


def test_size_suffixed_gpt_ids_are_the_small_tier():
    """mini and nano are the small tier in every generation — nano used to have
    no rule at all and fell through to opus."""
    by_id = {m.id: m for m in _seed_models()}
    suffixed = [m for m in by_id.values()
                if m.id.endswith("-mini") or m.id.endswith("-nano")]
    assert suffixed
    for model in suffixed:
        assert model.model_class == "haiku", (
            f"{model.id} classes {model.model_class}, expected haiku"
        )
