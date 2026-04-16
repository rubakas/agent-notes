"""Shared configuration, paths, and utilities."""

import os
import sys
from pathlib import Path

# --- Resolve project root ---
# When running from source: lib/agent_notes/config.py → ../../ = project root
# When installed via pip: use the package data location
def _find_root() -> Path:
    """Find the agent-notes project root directory."""
    # Try relative to this file (development mode)
    dev_root = Path(__file__).resolve().parent.parent.parent
    if (dev_root / "VERSION").exists() and (dev_root / "source").exists():
        return dev_root
    # Try AGENT_NOTES_DIR env var
    env_root = os.environ.get("AGENT_NOTES_DIR")
    if env_root:
        return Path(env_root)
    # Fallback
    return dev_root

ROOT = _find_root()
VERSION_FILE = ROOT / "VERSION"
SOURCE_DIR = ROOT / "source"
DIST_DIR = ROOT / "dist"

# Source paths
SOURCE_AGENTS_YAML = SOURCE_DIR / "agents.yaml"
SOURCE_AGENTS_DIR = SOURCE_DIR / "agents"
SOURCE_GLOBAL_MD = SOURCE_DIR / "global.md"
SOURCE_GLOBAL_COPILOT_MD = SOURCE_DIR / "global-copilot.md"
SOURCE_RULES_DIR = SOURCE_DIR / "rules"

# Dist paths
DIST_CLI_DIR = DIST_DIR / "cli"
DIST_CLAUDE_DIR = DIST_CLI_DIR / "claude"
DIST_OPENCODE_DIR = DIST_CLI_DIR / "opencode"
DIST_GITHUB_DIR = DIST_CLI_DIR / "github"
DIST_RULES_DIR = DIST_DIR / "rules"
DIST_SKILLS_DIR = DIST_DIR / "skills"

# Install target paths (global)
CLAUDE_HOME = Path.home() / ".claude"
OPENCODE_HOME = Path.home() / ".config" / "opencode"
GITHUB_HOME = Path.home() / ".github"
AGENTS_HOME = Path.home() / ".agents"

# Memory
MEMORY_DIR = CLAUDE_HOME / "agent-memory"
BACKUP_DIR = ROOT / "memory-backup"

# --- Colors ---
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    CYAN = "\033[0;36m"
    DIM = "\033[2m"
    NC = "\033[0m"  # No color

    @staticmethod
    def disable():
        """Disable colors (for non-TTY output)."""
        for attr in ("RED", "GREEN", "YELLOW", "CYAN", "DIM", "NC"):
            setattr(Color, attr, "")

# Disable colors if not a TTY
if not sys.stdout.isatty():
    Color.disable()

# --- Output helpers ---
def ok(msg: str) -> None:
    print(f"  {Color.GREEN}ok{Color.NC}  {msg}")

def warn(msg: str) -> None:
    print(f"  {Color.YELLOW}WARN{Color.NC}  {msg}")

def fail(msg: str) -> None:
    print(f"  {Color.RED}FAIL{Color.NC}  {msg}")

def error(msg: str) -> None:
    print(f"{Color.RED}Error: {msg}{Color.NC}", file=sys.stderr)
    sys.exit(1)

def info(msg: str) -> None:
    print(f"  {Color.GREEN}✓{Color.NC} {msg}")

def issue(msg: str) -> None:
    print(f"  {Color.RED}✗{Color.NC} {msg}")

def linked(path: str) -> None:
    print(f"  {Color.GREEN}LINKED{Color.NC}  {path}")

def removed(path: str) -> None:
    print(f"  {Color.GREEN}REMOVED{Color.NC}  {path}")

def skipped(path: str, reason: str = "not a symlink — remove manually") -> None:
    print(f"  {Color.YELLOW}SKIP{Color.NC}     {path} ({reason})")

def get_version() -> str:
    """Read version from VERSION file."""
    try:
        return VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        return "unknown"

def find_skill_dirs() -> list[Path]:
    """Find all skill directories (containing SKILL.md) in the repo."""
    skills = []
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            skills.append(d)
    return skills