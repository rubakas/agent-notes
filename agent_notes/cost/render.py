"""Render helpers for the cost-report subsystem.

Extracted from services/rendering.py so that rendering.py does not name
cost reporting directly.
"""


def include_skip(user_config: dict) -> set:
    """Return the set of include names to skip based on the cost_report_enabled preference.

    When cost reporting is disabled (the default), the cost_reporting shared-include
    is suppressed from built agent files and global claude.md / AGENTS.md.
    """
    return set() if user_config.get("cost_report_enabled", False) else {"cost_reporting"}
