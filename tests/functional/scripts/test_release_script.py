"""Smoke tests for scripts/release."""
import subprocess
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent
RELEASE_SCRIPT = REPO_ROOT / "scripts" / "release"

build_missing = shutil.which("python3") is None or subprocess.run(
    ["python3", "-c", "import build, twine"],
    capture_output=True,
).returncode != 0


@pytest.mark.skipif(build_missing, reason="build or twine not installed")
@pytest.mark.requires_clean_repo
def test_release_script_dry_run_exits_zero_on_clean_repo(tmp_path):
    result = subprocess.run(
        ["bash", str(RELEASE_SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        input="1\n",  # choose patch bump
    )
    assert result.returncode == 0, (
        f"--dry-run exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    dist_wheels = list((REPO_ROOT / "dist").glob("*.whl"))
    assert dist_wheels, "No .whl found in dist/ after dry run"


def test_release_script_help_documents_dry_run():
    result = subprocess.run(
        ["bash", str(RELEASE_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--dry-run" in result.stdout
