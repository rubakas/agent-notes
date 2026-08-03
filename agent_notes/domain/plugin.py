"""Plugin domain types — a toggleable agent-notes subsystem."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PluginHook:
    event: str                       # SessionStart / Stop / PreToolUse / PreCompact
    command: str                     # exact string from constants.Hooks — installed contract
    matcher: Optional[str] = None    # PreToolUse tool matcher, e.g. "Read|Bash|Grep"
    requires: Optional[str] = None   # backend.supports(...) capability gate


@dataclass(frozen=True)
class PluginAllow:
    value: str                       # settings.json allow entry, e.g. "Bash(agent-notes cost-report)"
    requires: Optional[str] = None


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    default: bool
    path: Path
    skills: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    hooks: tuple[PluginHook, ...] = ()
    allow: tuple[PluginAllow, ...] = ()
    stability: str = "stable"
