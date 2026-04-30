"""Pure-unit tests for cost_report and pricing helpers (no built_dist fixture)."""
import pytest
from pathlib import Path


def test_cost_report_not_standalone_script():
    """cost-report is now a subcommand of agent-notes, not a separate console_script."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    from pathlib import Path
    pyproject = Path(__file__).parents[3] / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    scripts = data["project"]["scripts"]
    assert "cost-report" not in scripts, "cost-report should not be a standalone console_script"
    assert "agent-notes" in scripts


def test_cost_report_module_imports():
    from agent_notes.scripts import cost_report
    assert callable(cost_report.main)


def test_pricing_yaml_loads():
    from agent_notes.scripts import _pricing
    data = _pricing._load()
    assert "baseline" in data
    assert "providers" in data


def test_normalize_model_dashed_to_dotted():
    from agent_notes.scripts import _pricing
    assert _pricing.normalize_model("claude-opus-4-7") == "claude-opus-4.7"
    assert _pricing.normalize_model("claude-sonnet-4-6") == "claude-sonnet-4.6"
