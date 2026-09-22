"""Tests that cache rates in pricing.yaml follow the file's stated convention.

seed.json carries no cache fields, so test_pricing_seed_divergence.py cannot see
cache drift at all — which is exactly where the Fable 5.1 overbill lived. Every
entry must therefore derive its cache rates from its input rate, and any real
deviation must be DECLARED below with a source, so that accidental drift fails.
"""
import pytest

from agent_notes.cost import _pricing


# Multiples of the input rate, as used throughout pricing.yaml.
CACHE_RATIOS = {
    "cache_read": 0.1,
    "cache_write_5m": 1.25,
    "cache_write_1h": 2.0,
}

# (provider, model) -> {"rates": {field: published rate}, "source": citation}.
#
# A bare domain is NOT a source: an earlier revision declared a 0.2x cache ratio
# for an "o-series (legacy)" row citing only `platform.openai.com/docs/pricing`,
# and the number turned out to be gpt-4o's price left behind when the `gpt-*`
# glob was deleted from that row. test_declared_deviation_cites_a_real_rate
# therefore requires the citation to name the model and quote the figure, so a
# declaration can only be added by someone who actually read a published rate.
DECLARED_DEVIATIONS = {
    ("Anthropic", "Claude Fable 5.1"): {
        "rates": {"cache_read": 0.25},
        "source": (
            "https://www.anthropic.com/pricing (checked 2026-09-19): Claude Fable 5.1 "
            "is published with a $0.25/MTok cache-read rate, not the usual 0.1x of "
            "its $10.00/MTok input rate."
        ),
    },
}

# OpenAI prices cached input but does not bill cache WRITES at all, so both write
# rates are 0.00 for every OpenAI entry. Source: https://platform.openai.com/docs/pricing
PROVIDERS_WITHOUT_CACHE_WRITES = {"OpenAI"}
CACHE_WRITE_FIELDS = ("cache_write_5m", "cache_write_1h")


def _rate_renderings(rate: float) -> set:
    """The plausible ways a published rate is written in prose ($0.25, 0.250)."""
    return {f"{rate:g}", f"{rate:.2f}", f"{rate:.3f}"}


def _priced_entries() -> list:
    """Yield (provider_name, model_name, price) for the baseline and every model."""
    pricing = _pricing._load()
    entries = [("baseline", pricing["baseline"]["label"], pricing["baseline"]["price"])]
    for provider in pricing.get("providers", []):
        for model in provider.get("models", []):
            entries.append((provider["name"], model["name"], model["price"]))
    return entries


CASES = [
    (provider, name, field, price)
    for provider, name, price in _priced_entries()
    for field in CACHE_RATIOS
]


@pytest.mark.parametrize(
    "provider,name,field,price",
    CASES,
    ids=[f"{p}/{n}/{f}" for p, n, f, _ in CASES],
)
def test_cache_rate_follows_convention(provider, name, field, price):
    actual = price[field]

    declared = DECLARED_DEVIATIONS.get((provider, name), {}).get("rates", {})
    if field in declared:
        assert actual == declared[field], (
            f"{provider}/{name}: {field} is {actual}, but the declared deviation "
            f"says {declared[field]} — update DECLARED_DEVIATIONS with a source "
            f"if the published rate changed"
        )
        return

    if provider in PROVIDERS_WITHOUT_CACHE_WRITES and field in CACHE_WRITE_FIELDS:
        assert actual == 0.00, (
            f"{provider}/{name}: {field} is {actual}; {provider} does not bill "
            f"cache writes, so it must be 0.00"
        )
        return

    expected = round(price["in"] * CACHE_RATIOS[field], 6)
    assert actual == expected, (
        f"{provider}/{name}: {field} is {actual}, expected {expected} "
        f"({CACHE_RATIOS[field]}x the ${price['in']}/MTok input rate). "
        f"If the provider publishes a different rate, add it to "
        f"DECLARED_DEVIATIONS with a source instead of changing this test"
    )


@pytest.mark.parametrize(
    "key",
    sorted(DECLARED_DEVIATIONS),
    ids=[f"{p}/{n}" for p, n in sorted(DECLARED_DEVIATIONS)],
)
def test_declared_deviation_cites_a_real_rate(key):
    """A deviation may only be declared with a source that names the model and
    quotes the rate. A bare domain lets an unverified number in silently."""
    provider, name = key
    declaration = DECLARED_DEVIATIONS[key]
    source = declaration.get("source", "")
    rates = declaration.get("rates", {})

    assert rates, f"{provider}/{name}: declares no rates"
    assert "://" in source, (
        f"{provider}/{name}: source {source!r} is not a citation — give a URL"
    )
    assert name in source, (
        f"{provider}/{name}: the source must name the model it prices; "
        f"a page-level citation cannot show which row the rate belongs to. "
        f"Got: {source!r}"
    )
    for field, rate in rates.items():
        assert any(r in source for r in _rate_renderings(rate)), (
            f"{provider}/{name}: the source must quote the {field} rate {rate} "
            f"it is declaring. Got: {source!r}"
        )


@pytest.mark.parametrize(
    "key",
    sorted(DECLARED_DEVIATIONS),
    ids=[f"{p}/{n}" for p, n in sorted(DECLARED_DEVIATIONS)],
)
def test_declared_deviation_matches_a_live_entry(key):
    """A declaration for a row that no longer exists is a stale exemption that
    would silently cover whatever row is added under that name next."""
    live = {(provider, name) for provider, name, _ in _priced_entries()}
    assert key in live, (
        f"{key[0]}/{key[1]} is declared in DECLARED_DEVIATIONS but has no entry "
        f"in pricing.yaml — remove the declaration along with the row"
    )
