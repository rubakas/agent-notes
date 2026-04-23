"""Diff installed state vs. newly built state."""

# Re-export for backward compatibility
from .domain.diff import ComponentDiff, StateDiff  # noqa: F401
from .services.diff import diff_scope_states, diff_states, render_diff_report, filter_diff

__all__ = ["ComponentDiff", "StateDiff", "diff_scope_states", "diff_states", "render_diff_report", "filter_diff"]