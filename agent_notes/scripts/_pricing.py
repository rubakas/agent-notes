"""Load pricing data and provide cost calculation helpers."""
import re
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


def normalize_model(m: str) -> str:
    """Normalize dash-separated version numbers to dotted form.

    claude-opus-4-7 -> claude-opus-4.7
    """
    return re.sub(r"-(\d+)-(\d+)\b", r"-\1.\2", m)


def _build_price_table(pricing: dict) -> list:
    rows = []
    for provider in pricing.get("providers", []):
        for model in provider.get("models", []):
            patterns = model["match"] if isinstance(model["match"], list) else [model["match"]]
            rows.append((patterns, model["price"]))
    return rows


def get_price(model_id: str) -> dict:
    pricing = _load()
    table = _build_price_table(pricing)
    for patterns, price in table:
        if any(fnmatch(model_id, p) for p in patterns):
            return price
    return {"in": 3.00, "out": 15.00, "cache": 0.30}


def calculate_cost(model_id: str, inp: int, outp: int, cache: int) -> float:
    p = get_price(model_id)
    return (inp * p["in"] + outp * p["out"] + cache * p["cache"]) / 1_000_000


def baseline_cost(inp: int, outp: int, cache: int) -> float:
    pricing = _load()
    p = pricing["baseline"]["price"]
    return (inp * p["in"] + outp * p["out"] + cache * p["cache"]) / 1_000_000


def baseline_label() -> str:
    return _load()["baseline"]["label"]
