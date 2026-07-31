"""Component lifecycle stability flag + development override.

A component (CLI backend, plugin, skill, agent, memory backend) may declare a
``stability`` of "stable" (default) or "wip". A "wip" component is hidden from the
wizard, the build, and user-facing listings unless its name appears in the
``AGENT_NOTES_ENABLE_WIP`` environment variable (comma-separated).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

STABILITY_STABLE = "stable"
STABILITY_WIP = "wip"
STABILITY_VALUES = frozenset({STABILITY_STABLE, STABILITY_WIP})

ENABLE_WIP_ENV = "AGENT_NOTES_ENABLE_WIP"


def normalize_stability(value, source: Optional[Path] = None) -> str:
    """Return a validated stability string, defaulting to "stable".

    ``None``/empty becomes "stable"; an unrecognised value raises ``ValueError``.
    """
    if value is None or value == "":
        return STABILITY_STABLE
    text = str(value).strip().lower()
    if text not in STABILITY_VALUES:
        where = f" in {source}" if source is not None else ""
        raise ValueError(
            f"Invalid stability {value!r}{where}; "
            f"expected one of {sorted(STABILITY_VALUES)}"
        )
    return text


def enabled_wip() -> frozenset[str]:
    """Component names force-enabled via AGENT_NOTES_ENABLE_WIP (may be empty)."""
    raw = os.environ.get(ENABLE_WIP_ENV, "")
    return frozenset(n.strip() for n in raw.split(",") if n.strip())


def is_visible(
    stability: str, name: str, override: Optional[frozenset[str]] = None
) -> bool:
    """True unless the component is "wip" and not force-enabled by the override."""
    if stability != STABILITY_WIP:
        return True
    if override is None:
        override = enabled_wip()
    return name in override
