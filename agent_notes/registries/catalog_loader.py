"""Catalog loader: compose seed.json + rules.yaml + user overrides into Model objects."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Optional

import yaml

from ..domain.model import Model
from ..config import DATA_DIR


CATALOG_DIR = DATA_DIR / "catalog"
USER_OVERRIDES_PATH = Path.home() / ".config" / "agent-notes" / "models.yaml"


def _match(pattern: str, model_id: str) -> bool:
    return fnmatch.fnmatch(model_id, pattern)


def _apply_family(model_id: str, families: list[dict]) -> str:
    for rule in families:
        if _match(rule["match"], model_id):
            return rule["family"]
    raise ValueError(f"No family rule matched '{model_id}'")


def _apply_class(model_id: str, classes: list[dict]) -> str:
    for rule in classes:
        if _match(rule["match"], model_id):
            return rule["class"]
    raise ValueError(f"No class rule matched '{model_id}'")


def _apply_capabilities(model_id: str, capabilities: dict) -> dict[str, bool]:
    caps: dict[str, bool] = dict(capabilities.get("default", {}))
    overrides = capabilities.get("overrides") or {}
    if model_id in overrides:
        caps.update(overrides[model_id])
    return caps


def _derive_openai_label(seed_id: str) -> str:
    """Derive display label from a dotted OpenAI seed id.

    'gpt-5.5'     → 'GPT-5.5'
    'gpt-5.4'     → 'GPT-5.4'
    'gpt-5.4-mini'→ 'GPT-5.4 Mini'
    """
    rest = seed_id[len("gpt-"):]          # "5.4-mini"
    parts = rest.split("-")               # ["5.4", "mini"]
    capitalized = [
        p.capitalize() if p and p[0].isalpha() else p
        for p in parts
    ]
    return "GPT-" + " ".join(capitalized)


def _normalize_openai_id(seed_id: str) -> str:
    """'gpt-5.4-mini' → 'gpt-5-4-mini'."""
    return seed_id.replace(".", "-")


def _load_yaml(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}")


def _merge_rules(base: dict, overrides: dict) -> dict:
    """Merge user-override rules onto base rules. User entries have higher priority."""
    merged: dict = dict(base)

    # families / classes: user rules are prepended (checked first)
    for key in ("families", "classes"):
        if key in overrides:
            merged[key] = list(overrides[key]) + list(base.get(key, []))

    # alias_transforms: user wins per provider
    if "alias_transforms" in overrides:
        merged["alias_transforms"] = {
            **base.get("alias_transforms", {}),
            **overrides["alias_transforms"],
        }

    # alias_overrides: deep merge, user wins
    if "alias_overrides" in overrides:
        base_ao: dict = {k: dict(v) for k, v in base.get("alias_overrides", {}).items()}
        for provider, models in overrides["alias_overrides"].items():
            base_ao.setdefault(provider, {}).update(models)
        merged["alias_overrides"] = base_ao

    # deprecated / never_default: union
    for key in ("deprecated", "never_default"):
        if key in overrides:
            combined = set(base.get(key, [])) | set(overrides[key])
            merged[key] = sorted(combined)

    # capabilities: merge default and overrides dicts
    if "capabilities" in overrides:
        base_caps = dict(base.get("capabilities", {}))
        user_caps = overrides["capabilities"]
        if "default" in user_caps:
            base_caps["default"] = {**base_caps.get("default", {}), **user_caps["default"]}
        if "overrides" in user_caps:
            base_cap_ovr = dict(base_caps.get("overrides", {}))
            for mid, caps in user_caps["overrides"].items():
                base_cap_ovr[mid] = {**base_cap_ovr.get(mid, {}), **caps}
            base_caps["overrides"] = base_cap_ovr
        merged["capabilities"] = base_caps

    return merged


def load_catalog(
    catalog_dir: Optional[Path] = None,
    overrides_path: Optional[Path] = None,
) -> list[Model]:
    """Load seed.json + rules.yaml + optional user overrides and return Model list."""
    if catalog_dir is None:
        catalog_dir = CATALOG_DIR

    seed_path = catalog_dir / "seed.json"
    with open(seed_path) as f:
        seed = json.load(f)

    rules_path = catalog_dir / "rules.yaml"
    rules = _load_yaml(rules_path)

    # Apply user overrides if present
    _overrides_path = USER_OVERRIDES_PATH if overrides_path is None else overrides_path
    if _overrides_path.exists():
        user_rules = _load_yaml(_overrides_path)
        rules = _merge_rules(rules, user_rules)

    families = rules.get("families", [])
    classes = rules.get("classes", [])
    alias_transforms = rules.get("alias_transforms", {})
    alias_overrides = rules.get("alias_overrides", {})
    deprecated_ids: set[str] = set(rules.get("deprecated", []))
    never_default_ids: set[str] = set(rules.get("never_default", []))
    capabilities = rules.get("capabilities", {})

    models: list[Model] = []

    for provider, entries in seed.get("providers", {}).items():
        for entry in entries:
            seed_id: str = entry["id"]

            if provider == "anthropic":
                model_id = seed_id
                label: str = entry.get("display_name") or seed_id
            elif provider == "openai":
                model_id = _normalize_openai_id(seed_id)
                label = _derive_openai_label(seed_id)
            else:
                model_id = seed_id
                label = entry.get("display_name") or seed_id

            family = _apply_family(model_id, families)
            model_class = _apply_class(model_id, classes)

            # Build alias using the transform template
            transform = alias_transforms.get(provider, "{id}")
            alias_value = transform.format(id=model_id, seed_id=seed_id)

            # Apply per-model alias override
            provider_overrides = alias_overrides.get(provider) or {}
            if model_id in provider_overrides:
                alias_value = provider_overrides[model_id]

            aliases: dict[str, str] = {provider: alias_value}

            caps = _apply_capabilities(model_id, capabilities)

            models.append(Model(
                id=model_id,
                label=label,
                family=family,
                model_class=model_class,
                aliases=aliases,
                capabilities=caps,
                deprecated=model_id in deprecated_ids,
                never_default=model_id in never_default_ids,
            ))

    return models
