"""End-to-end: the real binary in a pseudo-terminal, sandboxed HOME.

Skipped unless pexpect is installed — run it with
`uv run --with pexpect pytest tests/functional/test_install_review_pty.py`.
It renders into the repo's git-ignored agent_notes/dist/, like any build.
"""
import io
import os
import re
import subprocess
import sys

import pytest

pexpect = pytest.importorskip("pexpect")

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def test_install_review_end_to_end(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_CACHE_HOME=str(home / ".cache"), TERM="xterm-256color")
    child = pexpect.spawn(sys.executable, ["-m", "agent_notes", "install"], env=env,
                          cwd=str(home), dimensions=(24, 80), timeout=120, encoding="utf-8")
    log = io.StringIO()
    child.logfile_read = log
    child.expect("i install")
    child.send("i")
    child.expect("esc back")
    child.send("\r")
    child.expect(pexpect.EOF)
    child.close()
    output = log.getvalue()

    assert child.exitstatus == 0
    # Only the full-screen part must fit 80 columns; the post-install summary
    # printed after leaving the alternate screen may hold long paths.
    full_screen = output.split("\x1b[?1049l")[0]
    frames = [ANSI.sub("", frame) for frame in full_screen.split("\x1b[2J")[1:]]
    # The pty turns "\r\n" into "\r\r\n"; drop every "\r" before measuring width.
    assert frames, "no full-screen frames painted"
    assert all(len(line) <= 80 for frame in frames for line in frame.replace("\r", "").split("\n"))   # SC-002
    assert "Step 1 of" not in output                                                     # FR-001
    assert "Generating agent files" not in output                                        # SC-009
    # The recommendation, whatever it is today, read in the same sandbox
    # (user overrides and the catalog cache live under HOME): architect is a reasoner.
    reasoner = subprocess.run(
        [sys.executable, "-c",
         "from agent_notes.commands.wizard.role_models import Catalog, recommended_choices\n"
         "from agent_notes.registries.cli_registry import load_registry\n"
         "print(recommended_choices(Catalog(), load_registry().get('claude'))[0]['reasoner'])"],
        env=env, cwd=str(home), capture_output=True, text=True, check=True).stdout.strip()
    architect = home / ".claude" / "agents" / "architect.md"
    assert reasoner and f"model: {reasoner}\n" in architect.read_text()
