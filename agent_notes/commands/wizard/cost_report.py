"""Wizard step: ask whether to enable per-response cost reporting."""

from ...config import Color
from ...services.ui import _can_interactive, _radio_select, _radio_select_fallback


def _select_cost_report(step: int = 0, total: int = 0, version: str = '') -> bool:
    """Ask whether to enable cost reporting. Returns True to enable, False to disable.

    Default is No (disabled). Non-interactive installs skip the prompt and return False.
    """
    options = [
        ("No  (can enable later with: agent-notes config cost-report on)", "no"),
        ("Yes  (appends a token-usage table to every Claude response)", "yes"),
    ]

    if _can_interactive():
        result = _radio_select(
            "Enable per-response cost report?\n"
            "  (appends a token-usage table to every Claude Code / OpenCode response)",
            options,
            default=0,
            step=step,
            total=total,
            version=version,
        )
    else:
        result = _radio_select_fallback(
            "Enable per-response cost report?\n"
            "  (appends a token-usage table to every Claude Code / OpenCode response)",
            options,
            default=0,
            step=step,
            total=total,
            version=version,
        )

    enabled = result == "yes"
    label = "enabled" if enabled else "disabled"
    print(f"  {Color.GREEN}✓{Color.NC} Cost report: {label}")
    return enabled
