import json
import subprocess
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# NOTE: scripts/build-claude-plugin.sh and scripts/build-opencode-plugin.sh both
# hardcode their output root via `cd "$(dirname "$0")/.."` — they always write to the
# real repo root regardless of cwd. A tmp_path sandbox is not viable without modifying
# the scripts themselves (tracked as a script bug, out of scope for Phase 11.2).
# Until those scripts accept a configurable output root, these tests are marked
# requires_clean_repo so they are deselected from default runs and won't leave
# a dirty working tree that breaks test_release_script.py.

pytestmark = pytest.mark.requires_clean_repo


def test_build_plugins_orchestrator_help():
    result = subprocess.run([str(REPO_ROOT / "scripts/build-plugins"), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "claude" in result.stdout
    assert "opencode" in result.stdout


def test_build_claude_plugin_writes_manifest():
    subprocess.run([str(REPO_ROOT / "scripts/build-plugins"), "--cli", "claude"], check=True, capture_output=True)
    manifest = REPO_ROOT / ".claude-plugin/plugin.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert "name" in data
    assert "version" in data


def test_build_opencode_plugin_writes_index_js():
    subprocess.run([str(REPO_ROOT / "scripts/build-plugins"), "--cli", "opencode"], check=True, capture_output=True)
    js = REPO_ROOT / ".opencode-plugin/index.js"
    assert js.exists()
    text = js.read_text()
    assert "AgentNotes" in text
    assert "session.start" in text
    assert "Auto-generated" in text


def test_opencode_plugin_substitutes_version():
    subprocess.run([str(REPO_ROOT / "scripts/build-plugins"), "--cli", "opencode"], check=True, capture_output=True)
    version = (REPO_ROOT / "agent_notes/VERSION").read_text().strip()
    text = (REPO_ROOT / ".opencode-plugin/index.js").read_text()
    assert version in text
    assert "{{VERSION}}" not in text  # placeholder replaced


def test_opencode_plugin_no_unrendered_placeholders():
    subprocess.run([str(REPO_ROOT / "scripts/build-plugins"), "--cli", "opencode"], check=True, capture_output=True)
    text = (REPO_ROOT / ".opencode-plugin/index.js").read_text()
    assert "{{" not in text
    assert "}}" not in text


def test_build_plugins_both_default():
    result = subprocess.run([str(REPO_ROOT / "scripts/build-plugins")], capture_output=True, text=True)
    assert result.returncode == 0
    assert (REPO_ROOT / ".claude-plugin/plugin.json").exists()
    assert (REPO_ROOT / ".opencode-plugin/index.js").exists()


def test_build_plugins_invalid_cli_errors():
    result = subprocess.run([str(REPO_ROOT / "scripts/build-plugins"), "--cli", "nonsense"], capture_output=True, text=True)
    assert result.returncode != 0
