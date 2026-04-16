"""Install and uninstall agent-notes components."""

import shutil
from pathlib import Path
from typing import List

from .config import (
    ROOT, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME,
    linked, removed, skipped, info, get_version, find_skill_dirs, Color
)
from .build import build


def place_file(src: Path, dst: Path, copy_mode: bool = False) -> None:
    """Place file as symlink or copy, handling existing files."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    if copy_mode:
        if dst.exists() and not dst.is_symlink():
            skipped(str(dst), "exists, not a symlink")
            return
        if dst.is_symlink():
            dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        info(f"COPIED  {dst}")
    else:
        if dst.exists() and not dst.is_symlink():
            skipped(str(dst), "exists, not a symlink")
            return
        if dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)
        linked(str(dst))


def place_dir_contents(src_dir: Path, dst_dir: Path, pattern: str, copy_mode: bool = False) -> None:
    """Place all files matching pattern from src_dir to dst_dir."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_file in src_dir.glob(pattern):
        if src_file.exists():
            dst_file = dst_dir / src_file.name
            place_file(src_file, dst_file, copy_mode)


def install_skills_global(copy_mode: bool = False) -> None:
    """Install skills globally."""
    targets = [CLAUDE_HOME / "skills", OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in find_skill_dirs():
            place_file(skill_dir, target_dir / skill_dir.name, copy_mode)


def install_skills_local(copy_mode: bool = False) -> None:
    """Install skills locally."""
    targets = [Path(".claude/skills"), Path(".opencode/skills")]
    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in find_skill_dirs():
            place_file(skill_dir, target_dir / skill_dir.name, copy_mode)


def install_agents_global(copy_mode: bool = False) -> None:
    """Install agents globally."""
    print("Installing Claude Code agents to ~/.claude/agents/ ...")
    place_dir_contents(DIST_CLAUDE_DIR / "agents", CLAUDE_HOME / "agents", "*.md", copy_mode)

    print("Installing OpenCode agents to ~/.config/opencode/agents/ ...")
    place_dir_contents(DIST_OPENCODE_DIR / "agents", OPENCODE_HOME / "agents", "*.md", copy_mode)


def install_agents_local(copy_mode: bool = False) -> None:
    """Install agents locally."""
    print("Installing Claude Code agents to .claude/agents/ ...")
    place_dir_contents(DIST_CLAUDE_DIR / "agents", Path(".claude/agents"), "*.md", copy_mode)

    print("Installing OpenCode agents to .opencode/agents/ ...")
    place_dir_contents(DIST_OPENCODE_DIR / "agents", Path(".opencode/agents"), "*.md", copy_mode)


def install_rules_global(copy_mode: bool = False) -> None:
    """Install global config and rules."""
    print("Installing global config ...")

    # CLAUDE.md → ~/.claude/CLAUDE.md
    claude_global = DIST_CLAUDE_DIR / "CLAUDE.md"
    if claude_global.exists():
        place_file(claude_global, CLAUDE_HOME / "CLAUDE.md", copy_mode)

    # AGENTS.md → ~/.config/opencode/AGENTS.md
    agents_global = DIST_OPENCODE_DIR / "AGENTS.md"
    if agents_global.exists():
        place_file(agents_global, OPENCODE_HOME / "AGENTS.md", copy_mode)

    # Rules → ~/.claude/rules/
    if DIST_RULES_DIR.exists():
        place_dir_contents(DIST_RULES_DIR, CLAUDE_HOME / "rules", "*.md", copy_mode)

    # Copilot → ~/.github/copilot-instructions.md
    copilot_global = DIST_GITHUB_DIR / "copilot-instructions.md"
    if copilot_global.exists():
        place_file(copilot_global, GITHUB_HOME / "copilot-instructions.md", copy_mode)


def install_rules_local(copy_mode: bool = False) -> None:
    """Install local config and rules."""
    print("Installing project rules ...")

    # CLAUDE.md → ./CLAUDE.md
    claude_global = DIST_CLAUDE_DIR / "CLAUDE.md"
    if claude_global.exists():
        place_file(claude_global, Path("./CLAUDE.md"), copy_mode)

    # AGENTS.md → ./AGENTS.md
    agents_global = DIST_OPENCODE_DIR / "AGENTS.md"
    if agents_global.exists():
        place_file(agents_global, Path("./AGENTS.md"), copy_mode)

    # Rules → .claude/rules/
    if DIST_RULES_DIR.exists():
        place_dir_contents(DIST_RULES_DIR, Path(".claude/rules"), "*.md", copy_mode)


def remove_symlink(target: Path) -> None:
    """Remove symlink if it exists, skip non-symlinks."""
    if target.is_symlink():
        target.unlink()
        removed(str(target))
    elif target.exists():
        skipped(str(target))


def remove_symlinks_in_dir(dir_path: Path, pattern: str) -> None:
    """Remove symlinks matching pattern in directory."""
    if dir_path.exists():
        for f in dir_path.glob(pattern):
            if f.exists() or f.is_symlink():
                remove_symlink(f)


def uninstall_skills_global() -> None:
    """Uninstall skills globally."""
    targets = [CLAUDE_HOME / "skills", OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
    for target_dir in targets:
        if target_dir.exists():
            print(f"Removing skills from {target_dir} ...")
            for skill_dir in find_skill_dirs():
                remove_symlink(target_dir / skill_dir.name)


def uninstall_skills_local() -> None:
    """Uninstall skills locally."""
    targets = [Path(".claude/skills"), Path(".opencode/skills")]
    for target_dir in targets:
        if target_dir.exists():
            print(f"Removing skills from {target_dir} ...")
            for skill_dir in find_skill_dirs():
                remove_symlink(target_dir / skill_dir.name)


def uninstall_agents_global() -> None:
    """Uninstall agents globally."""
    print("Removing Claude Code agents from ~/.claude/agents/ ...")
    if (DIST_CLAUDE_DIR / "agents").exists():
        for f in (DIST_CLAUDE_DIR / "agents").glob("*.md"):
            if f.exists():
                remove_symlink(CLAUDE_HOME / "agents" / f.name)

    print("Removing OpenCode agents from ~/.config/opencode/agents/ ...")
    if (DIST_OPENCODE_DIR / "agents").exists():
        for f in (DIST_OPENCODE_DIR / "agents").glob("*.md"):
            if f.exists():
                remove_symlink(OPENCODE_HOME / "agents" / f.name)


def uninstall_agents_local() -> None:
    """Uninstall agents locally."""
    print("Removing Claude Code agents from .claude/agents/ ...")
    if (DIST_CLAUDE_DIR / "agents").exists():
        for f in (DIST_CLAUDE_DIR / "agents").glob("*.md"):
            if f.exists():
                remove_symlink(Path(".claude/agents") / f.name)

    print("Removing OpenCode agents from .opencode/agents/ ...")
    if (DIST_OPENCODE_DIR / "agents").exists():
        for f in (DIST_OPENCODE_DIR / "agents").glob("*.md"):
            if f.exists():
                remove_symlink(Path(".opencode/agents") / f.name)


def uninstall_rules_global() -> None:
    """Uninstall global config and rules."""
    print("Removing global config ...")
    remove_symlink(CLAUDE_HOME / "CLAUDE.md")
    remove_symlink(OPENCODE_HOME / "AGENTS.md")
    remove_symlink(GITHUB_HOME / "copilot-instructions.md")
    if DIST_RULES_DIR.exists():
        for f in DIST_RULES_DIR.glob("*.md"):
            if f.exists():
                remove_symlink(CLAUDE_HOME / "rules" / f.name)


def uninstall_rules_local() -> None:
    """Uninstall local config and rules."""
    print("Removing project rules ...")
    remove_symlink(Path("./CLAUDE.md"))
    remove_symlink(Path("./AGENTS.md"))
    if DIST_RULES_DIR.exists():
        for f in DIST_RULES_DIR.glob("*.md"):
            if f.exists():
                remove_symlink(Path(".claude/rules") / f.name)


def count_skills() -> int:
    """Count skill directories."""
    return len(find_skill_dirs())


def count_agents_claude() -> int:
    """Count Claude agent files."""
    agents_dir = DIST_CLAUDE_DIR / "agents"
    return len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0


def count_agents_opencode() -> int:
    """Count OpenCode agent files."""
    agents_dir = DIST_OPENCODE_DIR / "agents"
    return len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0


def count_global() -> int:
    """Count global config files."""
    count = 0
    if (DIST_CLAUDE_DIR / "CLAUDE.md").exists():
        count += 1
    if (DIST_OPENCODE_DIR / "AGENTS.md").exists():
        count += 1
    if (DIST_GITHUB_DIR / "copilot-instructions.md").exists():
        count += 1
    if DIST_RULES_DIR.exists():
        count += len(list(DIST_RULES_DIR.glob("*.md")))
    return count


def install(local: bool = False, copy: bool = False) -> None:
    """Build from source and install to targets."""
    # Validate args
    if copy and not local:
        print("Error: --copy is only valid with --local installs.")
        print("Global installs always use symlinks.")
        return

    # Build first
    print("Building from source...")
    try:
        build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    # Execute
    print(f"Installing ({'local' if local else 'global'}, {'copy' if copy else 'symlink'}) ...")
    print("")

    if local:
        install_skills_local(copy)
        install_agents_local(copy)
        install_rules_local(copy)
    else:
        install_skills_global(copy)
        install_agents_global(copy)
        install_rules_global(copy)

    print("")
    print(f"{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")


def uninstall(local: bool = False) -> None:
    """Remove installed components."""
    print(f"Uninstalling ({'local' if local else 'global'}) ...")
    print("")

    if local:
        uninstall_skills_local()
        uninstall_agents_local()
        uninstall_rules_local()
    else:
        uninstall_skills_global()
        uninstall_agents_global()
        uninstall_rules_global()

    print("")
    print(f"{Color.GREEN}Done.{Color.NC}")


def show_info() -> None:
    """Show installation status and component counts."""
    version = get_version()
    print(f"agent-notes {version}")
    print("")
    print("Components:")
    print(f"  Skills:              {count_skills()}")
    print(f"  Agents (Claude):     {count_agents_claude()}")
    print(f"  Agents (OpenCode):   {count_agents_opencode()}")
    print(f"  Global config:       {count_global()} files")
    print("")
    print("Install targets:")
    print("  Claude Code:   ~/.claude/")
    print("  OpenCode:      ~/.config/opencode/")
    print("  Copilot:       ~/.github/")
    print("  Universal:     ~/.agents/")
    print("")

    # Check install status
    global_ok = (CLAUDE_HOME / "agents").exists() and any((CLAUDE_HOME / "agents").iterdir())
    local_ok = Path(".claude/agents").exists() and any(Path(".claude/agents").iterdir())

    print("Status:")
    if global_ok:
        print(f"  Global:  {Color.GREEN}installed{Color.NC} (use doctor for details)")
    else:
        print(f"  Global:  {Color.YELLOW}not installed{Color.NC}")
    if local_ok:
        print(f"  Local:   {Color.GREEN}detected{Color.NC}")
    else:
        print(f"  Local:   {Color.CYAN}not detected{Color.NC}")