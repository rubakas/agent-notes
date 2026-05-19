"""Shared utility functions for memory backend implementations."""

from __future__ import annotations
import re
from datetime import datetime, timezone


def _slug(title: str) -> str:
    title = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\s*", "", title)
    title = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", title)
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now_hhmmss() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S")


_YAML_NEEDS_QUOTING = re.compile(r'[:{}\[\]|>\'\"*&!%@`#]')


def _yaml_safe(value: str) -> str:
    """Wrap value in double quotes if it contains YAML-special characters."""
    if not value:
        return value
    if _YAML_NEEDS_QUOTING.search(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a file into (frontmatter_dict, body_after_frontmatter).

    Returns an empty dict if the file does not start with '---'.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    rest = text[end + 4:].lstrip("\n")
    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, rest
