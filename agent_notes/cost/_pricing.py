"""Load pricing data and provide cost calculation helpers."""
import sys
from fnmatch import fnmatch
from importlib import resources

_pricing_cache = None


def _load() -> dict:
    global _pricing_cache
    if _pricing_cache is None:
        text = resources.files("agent_notes.data").joinpath("pricing.yaml").read_text()
        import yaml
        _pricing_cache = yaml.safe_load(text)
    return _pricing_cache


def _build_price_table(pricing: dict) -> list:
    rows = []
    for provider in pricing.get("providers", []):
        for model in provider.get("models", []):
            patterns = model["match"] if isinstance(model["match"], list) else [model["match"]]
            rows.append((patterns, model["price"]))
    return rows


# Fallback for an unmatched Anthropic id. Anthropic's lineup clusters around the
# Sonnet rate, so it is a defensible guess for a Claude id and nothing else: an
# OpenAI id billed at $3.00/$15.00 would be wrong by up to 60x and look plausible.
_ANTHROPIC_FALLBACK = {"in": 3.00, "out": 15.00, "cache_read": 0.30, "cache_write_5m": 3.75, "cache_write_1h": 6.00}

# Any other vendor's unmatched id is billed at zero rather than at a guessed
# number, so the warning is the only thing that can explain a missing cost.
_UNPRICED = {"in": 0.00, "out": 0.00, "cache_read": 0.00, "cache_write_5m": 0.00, "cache_write_1h": 0.00}


def get_price(model_id: str) -> dict:
    pricing = _load()
    table = _build_price_table(pricing)
    for patterns, price in table:
        if any(fnmatch(model_id, p) for p in patterns):
            return price
    if "claude" in model_id:
        sys.stderr.write(f"Warning: no pricing entry for model '{model_id}', falling back to Sonnet rates\n")
        return _ANTHROPIC_FALLBACK
    sys.stderr.write(
        f"Warning: no pricing entry for model '{model_id}'; it is not an Anthropic id, "
        f"so it is billed at $0.00 rather than at Claude rates — add an entry to pricing.yaml\n"
    )
    return _UNPRICED


def calculate_cost(
    model_id: str,
    inp: int,
    outp: int,
    cache_read: int = 0,
    cache_write_5m: int = 0,
    cache_write_1h: int = 0,
) -> float:
    p = get_price(model_id)
    # Support old pricing entries that still have a flat "cache" key
    read_rate = p.get("cache_read", p.get("cache", 0.0))
    write_5m_rate = p.get("cache_write_5m", p.get("cache", 0.0))
    write_1h_rate = p.get("cache_write_1h", p.get("cache", 0.0))
    return (
        inp * p["in"]
        + outp * p["out"]
        + cache_read * read_rate
        + cache_write_5m * write_5m_rate
        + cache_write_1h * write_1h_rate
    ) / 1_000_000


def baseline_cost(
    inp: int,
    outp: int,
    cache_read: int = 0,
    cache_write_5m: int = 0,
    cache_write_1h: int = 0,
) -> float:
    pricing = _load()
    p = pricing["baseline"]["price"]
    read_rate = p.get("cache_read", p.get("cache", 0.0))
    write_5m_rate = p.get("cache_write_5m", p.get("cache", 0.0))
    write_1h_rate = p.get("cache_write_1h", p.get("cache", 0.0))
    return (
        inp * p["in"]
        + outp * p["out"]
        + cache_read * read_rate
        + cache_write_5m * write_5m_rate
        + cache_write_1h * write_1h_rate
    ) / 1_000_000


def baseline_label() -> str:
    return _load()["baseline"]["label"]
