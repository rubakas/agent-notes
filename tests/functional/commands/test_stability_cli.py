import os
import sys
import subprocess
from pathlib import Path


def _run(tmp_path: Path, *args: str, extra_env=None):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "agent_notes", *args],
        env=env, capture_output=True, text=True,
    )


def test_doctor_reports_no_wip_by_default(tmp_path):
    result = _run(tmp_path, "doctor")
    # No shipped component is wip, so the doctor must not crash and must not
    # claim any wip components are active.
    assert result.returncode in (0, 1), f"stderr: {result.stderr}"
    assert "work-in-progress" not in result.stdout.lower() or "none" in result.stdout.lower()


def test_enable_wip_env_is_read(tmp_path):
    # An unknown override name must not crash any command.
    result = _run(tmp_path, "plugins", "list",
                  extra_env={"AGENT_NOTES_ENABLE_WIP": "does-not-exist"})
    assert result.returncode == 0, f"stderr: {result.stderr}"
