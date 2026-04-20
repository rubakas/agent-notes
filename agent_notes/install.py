"""Install and uninstall agent-notes components."""

import shutil
from pathlib import Path
from typing import List

from .config import (
    ROOT, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR, DIST_SKILLS_DIR,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME,
    linked, removed, skipped, info, get_version, Color
)
from .build import build


def _files_identical(a: Path, b: Path) -> bool:
    """Check if two files or directories have identical content."""
    try:
        if a.is_dir() and b.is_dir():
            # Compare directory contents recursively
            a_files = {f.relative_to(a): f.read_bytes() for f in a.rglob("*") if f.is_file()}
            b_files = {f.relative_to(b): f.read_bytes() for f in b.rglob("*") if f.is_file()}
            return a_files == b_files
        elif a.is_file() and b.is_file():
            return a.read_bytes() == b.read_bytes()
        return False
    except OSError:
        return False


def _handle_existing(src: Path, dst: Path) -> bool:
    """Handle an existing non-symlink destination file.
    
    Returns True if install should proceed, False to skip.
    """
    if _files_identical(src, dst):
        skipped(str(dst), "exists, identical content")
        return False
    
    print(f"\n  {Color.YELLOW}CONFLICT{Color.NC}  {dst}")
    print(f"             File exists and differs from source.")
    response = input("             (b)ackup and replace, (s)kip? [b/s] ").strip().lower()
    
    if response == 'b':
        backup_path = Path(str(dst) + ".bak")
        if dst.is_dir():
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(dst, backup_path)
            shutil.rmtree(dst)
        else:
            if backup_path.exists():
                backup_path.unlink()
            dst.rename(backup_path)
        print(f"  {Color.CYAN}BACKUP{Color.NC}   {backup_path}")
        return True
    else:
        skipped(str(dst), "user skipped")
        return False


def place_file(src: Path, dst: Path, copy_mode: bool = False) -> None:
    """Place file as symlink or copy, handling existing files."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    if copy_mode:
        if dst.exists() and not dst.is_symlink():
            if not _handle_existing(src, dst):
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
            if not _handle_existing(src, dst):
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
    if not DIST_SKILLS_DIR.exists():
        return
    targets = [CLAUDE_HOME / "skills", OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(DIST_SKILLS_DIR.iterdir()):
            if skill_dir.is_dir():
                place_file(skill_dir, target_dir / skill_dir.name, copy_mode)


def install_skills_local(copy_mode: bool = False) -> None:
    """Install skills locally."""
    if not DIST_SKILLS_DIR.exists():
        return
    targets = [Path(".claude/skills"), Path(".opencode/skills")]
    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(DIST_SKILLS_DIR.iterdir()):
            if skill_dir.is_dir():
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


def remove_all_symlinks_in_dir(dir_path: Path) -> None:
    """Remove all symlinks in a directory (files and dirs)."""
    if not dir_path.exists():
        return
    for item in dir_path.iterdir():
        if item.is_symlink():
            item.unlink()
            removed(str(item))
        elif item.exists():
            skipped(str(item))


def remove_dir_if_empty(dir_path: Path) -> None:
    """Remove directory if it exists and is empty."""
    try:
        if dir_path.exists() and not any(dir_path.iterdir()):
            dir_path.rmdir()
    except OSError:
        pass


def uninstall_skills_global() -> None:
    """Uninstall skills globally."""
    targets = [CLAUDE_HOME / "skills", OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
    for target_dir in targets:
        if target_dir.exists():
            print(f"Removing skills from {target_dir} ...")
            remove_all_symlinks_in_dir(target_dir)
            remove_dir_if_empty(target_dir)


def uninstall_skills_local() -> None:
    """Uninstall skills locally."""
    targets = [Path(".claude/skills"), Path(".opencode/skills")]
    for target_dir in targets:
        if target_dir.exists():
            print(f"Removing skills from {target_dir} ...")
            remove_all_symlinks_in_dir(target_dir)
            remove_dir_if_empty(target_dir)


def uninstall_agents_global() -> None:
    """Uninstall agents globally."""
    for label, agents_dir in [("Claude Code", CLAUDE_HOME / "agents"), ("OpenCode", OPENCODE_HOME / "agents")]:
        print(f"Removing {label} agents from {agents_dir} ...")
        remove_all_symlinks_in_dir(agents_dir)
        remove_dir_if_empty(agents_dir)


def uninstall_agents_local() -> None:
    """Uninstall agents locally."""
    for agents_dir in [Path(".claude/agents"), Path(".opencode/agents")]:
        print(f"Removing agents from {agents_dir} ...")
        remove_all_symlinks_in_dir(agents_dir)
        remove_dir_if_empty(agents_dir)


def uninstall_rules_global() -> None:
    """Uninstall global config and rules."""
    print("Removing global config ...")
    remove_symlink(CLAUDE_HOME / "CLAUDE.md")
    remove_symlink(OPENCODE_HOME / "AGENTS.md")
    remove_symlink(GITHUB_HOME / "copilot-instructions.md")
    rules_dir = CLAUDE_HOME / "rules"
    if rules_dir.exists():
        remove_all_symlinks_in_dir(rules_dir)
        remove_dir_if_empty(rules_dir)


def uninstall_rules_local() -> None:
    """Uninstall local config and rules."""
    print("Removing project rules ...")
    remove_symlink(Path("./CLAUDE.md"))
    remove_symlink(Path("./AGENTS.md"))
    rules_dir = Path(".claude/rules")
    if rules_dir.exists():
        remove_all_symlinks_in_dir(rules_dir)
        remove_dir_if_empty(rules_dir)


def count_skills() -> int:
    """Count skill directories."""
    if not DIST_SKILLS_DIR.exists():
        return 0
    return len([d for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()])


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