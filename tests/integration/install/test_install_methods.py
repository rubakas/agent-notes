"""Tests for the from-local-build install method (wheel build and contents)."""

import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


pytestmark = pytest.mark.requires_build


@pytest.fixture(scope="module")
def built_wheel():
    subprocess.run(["python3", "-m", "build", "--wheel"], cwd=REPO_ROOT, check=True, capture_output=True)
    wheels = list((REPO_ROOT / "dist").glob("agent_notes-*.whl"))
    assert wheels, "No wheel built"
    return max(wheels, key=lambda p: p.stat().st_mtime)  # most recent


def test_pyproject_declares_agent_notes_entry_point():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    text = (REPO_ROOT / "pyproject.toml").read_bytes()
    data = tomllib.loads(text.decode())
    scripts = data["project"]["scripts"]
    assert "agent-notes" in scripts
    assert "cost-report" in scripts


def test_pyproject_dynamic_version():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_bytes().decode())
    assert "version" in data["project"]["dynamic"]


def test_version_file_matches_2_3_0():
    assert (REPO_ROOT / "agent_notes" / "VERSION").read_text().strip() == "2.3.0"


def test_wheel_builds_clean(built_wheel):
    assert built_wheel.exists()
    assert built_wheel.stat().st_size > 1000  # sanity


def test_wheel_includes_data_files(built_wheel):
    with zipfile.ZipFile(built_wheel) as z:
        names = z.namelist()
    assert any("agent_notes/data/skills/" in n for n in names)
    assert any("agent_notes/data/agents/" in n for n in names)
    assert any("agent_notes/data/cli/" in n for n in names)


def test_wheel_includes_pricing_yaml(built_wheel):
    with zipfile.ZipFile(built_wheel) as z:
        names = z.namelist()
    assert any("agent_notes/data/pricing.yaml" in n for n in names)


def test_wheel_no_bin_wrapper_residue(built_wheel):
    """bin/agent-notes is gone; the wheel must not ship it."""
    with zipfile.ZipFile(built_wheel) as z:
        names = z.namelist()
    assert not any(n.endswith("bin/agent-notes") for n in names)
    assert not any(n.endswith("bin/cost-report") for n in names)
