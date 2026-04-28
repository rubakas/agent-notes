"""Shared test fixtures."""
import subprocess
import pytest
from pathlib import Path

from agent_notes.config import ROOT, DIST_DIR


@pytest.fixture(scope="session")
def built_dist():
    """Run the build once per session; skip all dependents if it fails."""
    result = subprocess.run(
        ["python3", "-m", "agent_notes", "build"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Build failed:\n{result.stdout}\n{result.stderr}")
    return DIST_DIR
