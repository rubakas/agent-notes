"""Equivalence gate: building with the default plugin set must not change dist.

A default-disabled plugin registry (zero manifests) must produce byte-identical
output to the pre-registry baseline.  This test is the contract that Task 3 of
the plugin-system plan (#35) is additive — the wiring code touches nothing.

Both fixture variants are exercised:
  state-local — empty XDG_CONFIG_HOME simulating a local-memory install
  state-none  — empty XDG_CONFIG_HOME simulating no configured state at all
Both must leave dist/ unchanged.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
_FIXTURES = REPO / "tests" / "fixtures"


def _build_and_diff(xdg_config_home: Path) -> str:
    """Run agent-notes build with the given XDG_CONFIG_HOME and return git diff output."""
    env = dict(os.environ, XDG_CONFIG_HOME=str(xdg_config_home))
    subprocess.run(
        [sys.executable, "-m", "agent_notes", "build"],
        cwd=REPO,
        env=env,
        check=True,
        capture_output=True,
    )
    diff = subprocess.run(
        ["git", "diff", "--stat", "agent_notes/dist/"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return diff.stdout.strip()


def test_default_build_is_byte_identical_state_local():
    """Build with state-local fixture must not alter any dist file."""
    drift = _build_and_diff(_FIXTURES / "state-local")
    assert drift == "", f"dist drifted (state-local):\n{drift}"


def test_default_build_is_byte_identical_state_none():
    """Build with state-none fixture must not alter any dist file."""
    drift = _build_and_diff(_FIXTURES / "state-none")
    assert drift == "", f"dist drifted (state-none):\n{drift}"
