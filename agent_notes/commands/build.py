"""Build agent configuration files from source."""

import yaml
import shutil
from pathlib import Path

from ..config import (
    AGENTS_YAML,
    DIST_DIR,
    info
)
from ..services.rendering import generate_agent_files, render_globals, load_agents_config


# Re-export for backward compatibility
def _load_frontmatter_template(template_name):
    """DEPRECATED: Use services.rendering._load_frontmatter_template instead."""
    from ..services.rendering import _load_frontmatter_template
    return _load_frontmatter_template(template_name)
def copy_global_files() -> list[Path]:
    """Copy global files and rules to destination."""
    from ..config import RULES_DIR, DIST_RULES_DIR
    
    copied_files = []
    
    # Use the rendering service for global files
    copied_files.extend(render_globals())
    
    # Copy all rules files
    if RULES_DIR.exists():
        # Build rule files
        DIST_RULES_DIR.mkdir(parents=True, exist_ok=True)
        for rule_file in RULES_DIR.glob('*.md'):
            dest_file = DIST_RULES_DIR / rule_file.name
            shutil.copy2(rule_file, dest_file)
            copied_files.append(dest_file)
    
    return copied_files


def copy_skills() -> list[Path]:
    """Copy skill directories to dist/skills/."""
    from ..config import find_skill_dirs
    
    dist_skills = DIST_DIR / "skills"
    # Clean and recreate
    if dist_skills.exists():
        shutil.rmtree(dist_skills)
    dist_skills.mkdir(parents=True, exist_ok=True)
    
    copied = []
    for skill_dir in find_skill_dirs():
        dest = dist_skills / skill_dir.name
        shutil.copytree(skill_dir, dest)
        copied.append(dest)
    return copied



def copy_commands() -> list[Path]:
    """Copy command files from data/commands/ to dist/claude/commands/."""
    from ..config import DATA_DIR, DIST_DIR
    src = DATA_DIR / "commands"
    if not src.exists():
        return []
    dest = DIST_DIR / "claude" / "commands"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in src.glob("*.md"):
        out = dest / f.name
        shutil.copy2(f, out)
        copied.append(out)
    return copied


def count_lines(file_path: Path) -> int:
    """Count lines in a file or all files within a directory."""
    try:
        if file_path.is_dir():
            return sum(
                len(f.read_text().splitlines())
                for f in file_path.rglob("*")
                if f.is_file()
            )
        return len(file_path.read_text().splitlines())
    except Exception:
        return 0


def build() -> None:
    """Build agent configuration files from source."""
    from .. import state as state_module
    from ..config import ROOT
    
    # Read configuration
    try:
        agents_config, tiers = load_agents_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    
    # Load state if present (no error if missing)
    state = state_module.load()
    
    # Generate agent files (state=None is backward compatible)
    print("Generating agent files...")
    agent_files = generate_agent_files(agents_config, tiers, state=state)
    
    # Copy global files
    print("Copying global files...")
    global_files = copy_global_files()
    
    # Copy skills
    print("Copying skills...")
    skill_files = copy_skills()

    # Copy commands
    print("Copying commands...")
    command_files = copy_commands()

    # Report results
    all_files = agent_files + global_files + skill_files + command_files
    print(f"\nGenerated {len(all_files)} files:")
    
    total_lines = 0
    for file_path in sorted(all_files):
        try:
            rel_path = file_path.relative_to(ROOT)
        except ValueError:
            rel_path = file_path  # absolute path if outside the package tree
        lines = count_lines(file_path)
        total_lines += lines
        print(f"  {rel_path} ({lines} lines)")
    
    print(f"\nTotal: {total_lines} lines across {len(all_files)} files")


if __name__ == '__main__':
    build()