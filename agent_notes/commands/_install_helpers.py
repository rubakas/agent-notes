"""Shared installation helpers for install/uninstall/info commands."""

import shutil
from pathlib import Path
from typing import List

from ..config import (
    ROOT, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR, DIST_SKILLS_DIR,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME, BIN_HOME,
    linked, removed, skipped, info, get_version, Color, PKG_DIR
)
from ..services.fs import (
    files_identical as _files_identical,
    handle_existing as _handle_existing,
    place_file, place_dir_contents, remove_symlink, 
    remove_all_symlinks_in_dir, remove_dir_if_empty
)



def _install_skills_to(targets: List[Path], dist_skills_dir: Path, copy_mode: bool) -> None:
    """Install skills from dist_skills_dir to each directory in targets."""
    if not dist_skills_dir.exists():
        return
    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(dist_skills_dir.iterdir()):
            if skill_dir.is_dir():
                place_file(skill_dir, target_dir / skill_dir.name, copy_mode)


def install_skills_global(copy_mode: bool = False) -> None:
    """Install skills globally."""
    targets = [CLAUDE_HOME / "skills", OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
    _install_skills_to(targets, DIST_SKILLS_DIR, copy_mode)


def install_skills_local(copy_mode: bool = False) -> None:
    """Install skills locally."""
    targets = [Path(".claude/skills"), Path(".opencode/skills")]
    _install_skills_to(targets, DIST_SKILLS_DIR, copy_mode)


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



def _uninstall_skills_from(targets: List[Path]) -> None:
    """Remove skills from each directory in targets."""
    for target_dir in targets:
        if target_dir.exists():
            print(f"Removing skills from {target_dir} ...")
            remove_all_symlinks_in_dir(target_dir)
            remove_dir_if_empty(target_dir)


def uninstall_skills_global() -> None:
    """Uninstall skills globally."""
    from .. import config
    targets = [config.CLAUDE_HOME / "skills", config.OPENCODE_HOME / "skills", config.AGENTS_HOME / "skills"]
    _uninstall_skills_from(targets)


def uninstall_skills_local() -> None:
    """Uninstall skills locally."""
    _uninstall_skills_from([Path(".claude/skills"), Path(".opencode/skills")])


def _uninstall_agents_from(dirs: List[Path]) -> None:
    """Remove agent symlinks from each directory in dirs."""
    for agents_dir in dirs:
        print(f"Removing agents from {agents_dir} ...")
        remove_all_symlinks_in_dir(agents_dir)
        remove_dir_if_empty(agents_dir)


def uninstall_agents_global() -> None:
    """Uninstall agents globally."""
    from .. import config
    _uninstall_agents_from([config.CLAUDE_HOME / "agents", config.OPENCODE_HOME / "agents"])


def uninstall_agents_local() -> None:
    """Uninstall agents locally."""
    _uninstall_agents_from([Path(".claude/agents"), Path(".opencode/agents")])


def _uninstall_rules_from(config_symlinks: List[Path], rules_dir: Path, label: str) -> None:
    """Remove config symlinks and rules directory."""
    print(label)
    for symlink in config_symlinks:
        remove_symlink(symlink)
    if rules_dir.exists():
        remove_all_symlinks_in_dir(rules_dir)
        remove_dir_if_empty(rules_dir)


def uninstall_rules_global() -> None:
    """Uninstall global config and rules."""
    from .. import config
    _uninstall_rules_from(
        [config.CLAUDE_HOME / "CLAUDE.md", config.OPENCODE_HOME / "AGENTS.md", config.GITHUB_HOME / "copilot-instructions.md"],
        config.CLAUDE_HOME / "rules",
        "Removing global config ...",
    )


def uninstall_rules_local() -> None:
    """Uninstall local config and rules."""
    _uninstall_rules_from(
        [Path("./CLAUDE.md"), Path("./AGENTS.md")],
        Path(".claude/rules"),
        "Removing project rules ...",
    )



def count_skills() -> int:
    """Count skill directories."""
    if not DIST_SKILLS_DIR.exists():
        return 0
    return len([d for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()])


def count_agents(backend) -> int:
    """Count agent *.md files in backend's dist directory. Returns 0 if backend
    doesn't support agents."""
    from ..services import installer
    from ..domain.cli_backend import CLIBackend
    if not backend.supports("agents"):
        return 0
    src = installer.dist_source_for(backend, "agents")
    if src is None or not src.exists():
        return 0
    return len(list(src.glob("*.md")))


def count_global() -> int:
    """Count global config files."""
    count = 0

    # Check each potential global config file (maintaining backward compatibility)
    if (DIST_CLAUDE_DIR / "CLAUDE.md").exists():
        count += 1
    if (DIST_OPENCODE_DIR / "AGENTS.md").exists():
        count += 1
    if (DIST_GITHUB_DIR / "copilot-instructions.md").exists():
        count += 1

    # Count rules files
    if DIST_RULES_DIR.exists():
        count += len(list(DIST_RULES_DIR.glob("*.md")))

    return count


def _verify_install(scope_state, scope, project_path, registry) -> list[str]:
    """Check each file recorded in scope_state.installed exists. Return list of missing issues."""
    from pathlib import Path
    issues = []
    for cli_name, backend_state in scope_state.clis.items():
        try:
            backend = registry.get(cli_name)
        except KeyError:
            issues.append(f"CLI '{cli_name}' no longer in registry")
            continue
        # Print per-component counts
        for component_type, items in backend_state.installed.items():
            present = 0
            missing_names = []
            for name, item in items.items():
                if Path(item.target).exists() or Path(item.target).is_symlink():
                    present += 1
                else:
                    missing_names.append(name)
            total = len(items)
            if missing_names:
                comp_label = f"{backend.label} {component_type}"
                print(f"  ✗ {comp_label}: {len(missing_names)} missing ({', '.join(missing_names[:3])}{'...' if len(missing_names) > 3 else ''})")
                for m in missing_names:
                    issues.append(f"{comp_label}: {m} missing")
            else:
                if total > 0:
                    if component_type == "config":
                        comp_label = f"{backend.label} config"
                    else:
                        comp_label = f"{backend.label} {component_type}"
                    print(f"  ✓ {total} {comp_label} present")
    return issues