"""Model dataclass — pure data model for model descriptors."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Model:
    id: str                          # "claude-opus-4-7"
    label: str                       # "Claude Opus 4.7"
    family: str                      # "claude", "kimi", "gpt"
    model_class: str                 # "opus" | "sonnet" | "haiku" | "flash" | "pro"
    aliases: dict[str, str]          # {"anthropic": "claude-opus-4-7", ...}
    pricing: dict[str, float] = field(default_factory=dict)
    capabilities: dict[str, bool] = field(default_factory=dict)

    def has_alias_for(self, provider: str) -> bool:
        return provider in self.aliases

    def resolve_for_providers(self, providers: list[str]) -> Optional[tuple[str, str]]:
        """Given a CLI's ordered accepted_providers list, return (provider, resolved_id)
        for the first provider that has an alias for this model. None if no compat."""
        for provider in providers:
            if provider in self.aliases:
                return (provider, self.aliases[provider])
        return None